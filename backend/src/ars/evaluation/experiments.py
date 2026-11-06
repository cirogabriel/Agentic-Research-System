"""Ejecución de experimentos A/B/C y de la evaluación de recuperación."""
from __future__ import annotations

import logging
import time
from typing import Any

from ars.agents import prompts
from ars.config import Settings
from ars.evaluation import agent_metrics, generation_metrics, retrieval_metrics
from ars.evaluation.agent_metrics import RunOutcome
from ars.graph.nodes import GraphOptions
from ars.graph.reporter import MemoryReporter
from ars.graph.runner import run_research
from ars.llm.budget import UsageTracker
from ars.schemas.agents import BaselineAnswer
from ars.schemas.rag import RetrievalRequest
from ars.security import wrap_untrusted

log = logging.getLogger(__name__)
KS = (1, 3, 5)


def flatten(summary: dict[str, Any]) -> dict[str, float]:
    """{'retrieval': {'mrr': 1}} → {'retrieval.mrr': 1}; solo valores numéricos."""
    flat: dict[str, float] = {}
    for section, values in summary.items():
        if isinstance(values, dict):
            flat.update({f"{section}.{k}": float(v) for k, v in values.items() if isinstance(v, (int, float))})
    return flat


class ExperimentRunner:
    def __init__(self, container: Any) -> None:
        self.c = container
        self.settings: Settings = container.settings

    # ---- un ítem de recuperación ----
    def run_retrieval_item(self, item: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
        self.c.retrieval.cache.clear()  # la caché falsearía la latencia medida
        req = RetrievalRequest(query=item["question"], strategy=cfg.get("retrieval_strategy", "hybrid"), transform="none",
                               top_k=min(50, max(KS) * 3), rerank=cfg.get("rerank"))
        res = self.c.retrieval.retrieve(req)
        docs = retrieval_metrics.dedupe_ranking(ch.document_name for ch in res.chunks)
        metrics = retrieval_metrics.evaluate_ranking(docs, set(item.get("relevant_documents", [])), KS)
        metrics["retrieval_latency_ms"] = float(res.latency_ms)
        return {"metrics": metrics, "retrieved": docs, "answer": None, "latency_ms": res.latency_ms, "tokens_in": 0, "tokens_out": 0, "iterations": 0, "outcome": None}

    # ---- A: RAG convencional (una consulta, una llamada al LLM) ----
    def run_baseline_item(self, item: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
        t0 = time.perf_counter()
        self.c.retrieval.cache.clear()
        tracker = self.c.new_tracker(cfg.get("token_budget"))
        llm = self.c.new_llm(tracker)
        res = self.c.retrieval.retrieve(RetrievalRequest(query=item["question"], strategy=cfg.get("retrieval_strategy", "hybrid"), transform="none",
                                                         top_k=cfg.get("top_k", 5), rerank=cfg.get("rerank")), tracker=tracker)
        labels = {f"S{i}": ch for i, ch in enumerate(res.chunks, start=1)}
        ctx = "\n".join(wrap_untrusted(lb, ch.content, source=ch.document_name) for lb, ch in labels.items())
        status, answer = "completed", ""
        try:
            answer = llm.structured(BaselineAnswer, system=prompts.BASELINE, user=f"<question>{item['question']}</question>\n<context>\n{ctx}\n</context>", use_reserve=True).answer
        except Exception as exc:
            status = "failed"
            log.warning("Baseline falló: %s", exc)
        latency = int((time.perf_counter() - t0) * 1000)
        docs = retrieval_metrics.dedupe_ranking(ch.document_name for ch in res.chunks)
        rel = set(item.get("relevant_documents", []))
        ok, total = generation_metrics.citation_validity(answer, set(labels))
        outcome = RunOutcome(item["id"], status, answer, latency, tracker.tokens_in, tracker.tokens_out, 1, [], [], [res.decision.strategy], ok, total,
                             retrieval_metrics.recall_at_k(docs, rel, cfg.get("top_k", 5)), item.get("expected_keywords", []), item.get("expected_strategy"), item.get("expected_aspects", []))
        return self._finish(item, answer, [ch.content for ch in res.chunks], docs, [ch.document_name for ch in res.chunks], set(labels), tracker, outcome, status)

    # ---- B / C: sistema multiagente ----
    def run_agent_item(self, item: dict[str, Any], cfg: dict[str, Any], mode: str) -> dict[str, Any]:
        t0 = time.perf_counter()
        self.c.retrieval.cache.clear()
        tracker = self.c.new_tracker(cfg.get("token_budget"))
        reporter = MemoryReporter()
        options = GraphOptions(parallel=(mode == "C"), verify_with_llm=(mode == "C"), allow_reinvestigation=(mode == "C"), max_iterations=cfg.get("max_iterations"),
                               top_k=cfg.get("top_k", 5), strategy=cfg.get("retrieval_strategy", "auto"))
        final = run_research(settings=self.settings, query=item["question"], options=options, reporter=reporter, tracker=tracker, thread_id=f"eval-{mode}-{item['id']}-{int(t0)}",
                             retrieval=self.c.retrieval, llm=self.c.new_llm(tracker), checkpointer=None, skip_clarification=True)
        latency = int((time.perf_counter() - t0) * 1000)
        sources = final.get("sources", {})
        ordered = sorted(sources.values(), key=lambda s: -s["score"])
        report = final.get("report") or {}
        content = report.get("content", {})
        total, invalid = content.get("citations_total", 0), content.get("citations_invalid", 0)
        status = final.get("status", "failed")
        outcome = RunOutcome(item["id"], status, report.get("markdown", ""), latency, tracker.tokens_in, tracker.tokens_out, final.get("iteration", 1), reporter.executions,
                             final.get("tasks", []), sorted({r["strategy"] for r in final.get("task_results", []) if r.get("strategy")}), total - invalid, total,
                             final.get("verification", {}).get("coverage", 0.0), item.get("expected_keywords", []), item.get("expected_strategy"), item.get("expected_aspects", []))
        docs = retrieval_metrics.dedupe_ranking(s["document_name"] for s in ordered)
        return self._finish(item, report.get("markdown", ""), [s["text"] for s in ordered], docs, [s["document_name"] for s in ordered], set(sources), tracker, outcome, status,
                            gen_answer=report.get("summary", "") + "\n" + "\n".join(f["statement"] for f in final.get("findings", []) if f.get("support") == "supported"))

    def _finish(self, item: dict[str, Any], answer: str, contexts: list[str], docs: list[str], chunk_docs: list[str], labels: set[str], tracker: UsageTracker,
                outcome: RunOutcome, status: str, gen_answer: str | None = None) -> dict[str, Any]:
        rel = set(item.get("relevant_documents", []))
        metrics = retrieval_metrics.evaluate_ranking(docs, rel, KS)
        # Para generación se usa el texto "limpio" (resumen + hechos respaldados) en B/C y la respuesta completa en A.
        metrics.update(generation_metrics.evaluate_generation(item["question"], gen_answer or answer, contexts, item.get("reference_answer")))
        metrics["context_precision_doc"] = round(generation_metrics.context_precision_doc(chunk_docs, rel), 4)
        metrics["citation_accuracy"] = round(outcome.citations_ok / outcome.citations_total, 4) if outcome.citations_total else 0.0
        metrics["cost_usd"] = tracker.cost_usd
        return {"metrics": metrics, "retrieved": docs, "answer": answer, "latency_ms": outcome.latency_ms, "tokens_in": tracker.tokens_in, "tokens_out": tracker.tokens_out,
                "iterations": outcome.iterations, "outcome": outcome, "status": status, "contexts": contexts}

    # ---- resumen ----
    def summarize(self, mode: str, results: list[dict[str, Any]]) -> dict[str, Any]:
        ok = [r for r in results if r.get("status", "completed") != "error"]
        retr_keys = {k for r in ok for k in r["metrics"] if k.startswith(("recall@", "precision@", "ndcg@")) or k in {"mrr", "retrieval_latency_ms"}}
        retrieval = retrieval_metrics.mean_metrics([{k: v for k, v in r["metrics"].items() if k in retr_keys} for r in ok])
        summary: dict[str, Any] = {"retrieval": retrieval}
        if mode != "retrieval":
            gen_keys = ("faithfulness_lexical", "answer_relevancy_lexical", "answer_correctness_f1", "context_recall_lexical", "context_precision_doc")
            summary["generation"] = retrieval_metrics.mean_metrics([{k: v for k, v in r["metrics"].items() if k in gen_keys} for r in ok])
            summary["agent"] = agent_metrics.summarize([r["outcome"] for r in ok if r.get("outcome")])
            tin, tout = sum(r["tokens_in"] for r in ok), sum(r["tokens_out"] for r in ok)
            s = self.settings
            summary["cost"] = {"tokens_total": tin + tout, "cost_usd_total": round((tin * s.llm_price_input_per_mtok + tout * s.llm_price_output_per_mtok) / 1e6, 6),
                               "cost_usd_per_item": round((tin * s.llm_price_input_per_mtok + tout * s.llm_price_output_per_mtok) / 1e6 / max(1, len(ok)), 6)}
        summary["meta"] = {"items_total": len(results), "items_failed": len(results) - len(ok)}
        return summary
