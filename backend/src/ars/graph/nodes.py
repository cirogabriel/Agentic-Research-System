from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.graph import END
from langgraph.types import Send

from ars.agents.analysis import AnalysisAgent
from ars.agents.evidence import merge_sources, select_evidence
from ars.agents.report import ReportAgent
from ars.agents.research import ResearchAgent
from ars.agents.supervisor import SupervisorAgent
from ars.agents.toolbox import RetrievalToolbox
from ars.agents.verification import VerificationAgent
from ars.config import Settings
from ars.exceptions import BudgetExceededError
from ars.graph.context import build_notes, prune_messages
from ars.graph.reporter import MemoryReporter
from ars.graph.state import ResearchState, WorkerInput
from ars.llm.base import StructuredLLM
from ars.llm.budget import UsageTracker
from ars.query.processor import QueryProcessor
from ars.schemas.agents import SubTask
from ars.schemas.query import QueryAnalysis
from ars.schemas.rag import SearchFilters

log = logging.getLogger(__name__)


@dataclass
class GraphOptions:

    parallel: bool = True
    verify_with_llm: bool = True
    allow_reinvestigation: bool = True
    max_iterations: int | None = None
    max_subtasks: int | None = None
    top_k: int = 5
    strategy: str = "auto"
    transform: str = "auto"
    filters: SearchFilters | None = None


@dataclass
class GraphDeps:
    settings: Settings
    llm: StructuredLLM
    tracker: UsageTracker
    toolbox: RetrievalToolbox
    reporter: MemoryReporter
    options: GraphOptions = field(default_factory=GraphOptions)


def _note(name: str, text: str) -> AIMessage:
    return AIMessage(content=text, name=name)


class ResearchNodes:
    def __init__(self, deps: GraphDeps) -> None:
        self.d, o = deps, deps.options
        self.rep, self.tracker, self.settings = (
            deps.reporter,
            deps.tracker,
            deps.settings,
        )
        self.query_processor = QueryProcessor(deps.llm, deps.settings)
        self.supervisor = SupervisorAgent(
            deps.llm,
            deps.settings,
            max_subtasks=o.max_subtasks,
            max_iterations=o.max_iterations,
        )
        self.researcher = ResearchAgent(
            deps.toolbox, o.top_k, o.filters, o.strategy, o.transform
        )
        self.analyst = AnalysisAgent(deps.llm, deps.settings)
        self.verifier = VerificationAgent(
            deps.llm, deps.settings, use_llm=o.verify_with_llm
        )
        self.reporter_agent = ReportAgent(deps.llm)

    def _fail(self, exc: Exception, where: str) -> dict[str, Any]:
        log.exception("Error en nodo %s", where)
        self.rep.event("research.failed", f"Error en {where}: {exc}")
        return {
            "failed": True,
            "status": "failed",
            "stop_reason": "error",
            "errors": [f"{where}: {type(exc).__name__}: {exc}"[:500]],
        }

    # ---- Recepción y comprensión de la consulta ----
    def understand(self, state: ResearchState) -> dict[str, Any]:
        self.rep.stage("understanding")
        self.rep.event("research.started", "Investigación iniciada")
        try:
            with self.rep.execution("query_processor") as rec:
                analysis = self.query_processor.process(
                    state["query"],
                    parent_context=state.get("parent_context", ""),
                    rec=rec,
                )
        except Exception as exc:
            return self._fail(exc, "understand")
        self.rep.event(
            "query.analyzed",
            f"Tema: {analysis.topic}",
            {
                "research_type": analysis.research_type,
                "used_llm": analysis.used_llm,
            },
        )
        update: dict[str, Any] = {
            "analysis": analysis.model_dump(),
            "iteration": 0,
            "messages": [
                _note(
                    "query_processor",
                    f"topic={analysis.topic}; type={analysis.research_type}; aspects={', '.join(analysis.key_aspects)}",
                )
            ],
        }
        if analysis.is_ambiguous and not state.get("skip_clarification"):
            self.rep.event(
                "research.needs_clarification",
                "Se requieren aclaraciones",
                {"questions": analysis.clarification_questions},
            )
            update.update(
                status="needs_clarification", stop_reason="needs_clarification"
            )
        elif not analysis.needs_research:
            text = analysis.direct_answer or analysis.objective
            update.update(
                status="completed",
                stop_reason="no_research_needed",
                report={
                    "title": "Respuesta directa",
                    "markdown": text,
                    "summary": text[:300],
                    "degraded": False,
                    "content": {},
                },
                quality={
                    "note": "La consulta no requería investigación documental"
                },
            )
            self.rep.event(
                "research.completed", "Respuesta directa sin investigación"
            )
        self.rep.sync_usage(self.tracker)
        return update

    def route_after_understand(self, state: ResearchState) -> str:
        return (
            "end"
            if state.get("status")
            in {"needs_clarification", "completed", "failed"}
            else "plan"
        )

    # ---- Planificación y subtareas ----
    def plan(self, state: ResearchState) -> dict[str, Any]:
        self.rep.stage("planning")
        try:
            with self.rep.execution("supervisor", iteration=1) as rec:
                tasks, rationale = self.supervisor.plan(
                    QueryAnalysis(**state["analysis"]),
                    state.get("parent_context", ""),
                    rec,
                )
        except Exception as exc:
            return self._fail(exc, "plan")
        dumped = [t.model_dump() for t in tasks]
        self.rep.event(
            "plan.created",
            f"{len(tasks)} subtarea(s) planificada(s)",
            {"rationale": rationale, "tasks": [t.title for t in tasks]},
        )
        self.rep.sync_usage(self.tracker, 1)
        return {
            "tasks": dumped,
            "pending": dumped,
            "iteration": 1,
            "messages": [
                _note(
                    "supervisor",
                    f"plan: {rationale} | "
                    + "; ".join(f"{t.id}={t.title}" for t in tasks),
                )
            ],
        }

    # ---- Delegación: fan-out hacia los Research Agents ----
    def fan_out(self, state: ResearchState) -> list[Send] | str:
        if state.get("failed") or not state.get("pending"):
            return END
        it, pending = state.get("iteration", 1), state["pending"]
        if self.d.options.parallel:
            return [
                Send("research_worker", {"tasks": [t], "iteration": it})
                for t in pending
            ]  # un worker por subtarea, en paralelo
        return [
            Send("research_worker", {"tasks": pending, "iteration": it})
        ]  # un único worker, subtareas en serie

    # ---- Worker de investigación ----
    def research_worker(self, payload: WorkerInput) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for t in payload["tasks"]:
            task = SubTask(**t)
            self.rep.event(
                "task.started", f"Buscando: {task.title}", {"task": task.id}
            )
            with self.rep.execution(
                "research", task_key=task.id, iteration=payload["iteration"]
            ) as rec:
                result = self.researcher.run(task, rec)
                rec.error = result.error 
            self.rep.event(
                "task.completed",
                f"{task.title}: {len(result.evidence)} fragmento(s)",
                {
                    "task": task.id,
                    "strategy": result.strategy,
                    "transform": result.transform,
                    "error": result.error,
                },
            )
            results.append(result.model_dump(mode="json"))
        return {"task_results": results}

    # ---- Análisis ----
    def analyze(self, state: ResearchState) -> dict[str, Any]:
        self.rep.stage("analyzing")
        it = state.get("iteration", 1)
        current = [
            r for r in state.get("task_results", []) if r["iteration"] == it
        ]
        update_sources, used = select_evidence(
            current,
            state.get("sources", {}),
            per_task=self.settings.evidence_per_task,
            max_chars=self.settings.analysis_max_evidence_chars,
        )
        merged = merge_sources(state.get("sources", {}), update_sources)
        previous = state.get("findings", [])
        out: dict[str, Any] = {
            "sources": update_sources,
            "analysis_failed": False,
        }
        if (
            not used and not previous
        ):  
            out.update(
                findings=[],
                analysis_notes={
                    "gaps": ["No se recuperó evidencia para la consulta."]
                },
            )
            self.rep.event("analysis.completed", "Sin evidencia que analizar")
            return out
        try:
            notes = build_notes(
                state.get("messages", []),
                {"verification", "supervisor"},
                self.settings.message_context_tokens,
            )
            with self.rep.execution("analysis", iteration=it) as rec:
                res = self.analyst.analyze(
                    analysis=QueryAnalysis(**state["analysis"]),
                    tasks=state["tasks"],
                    sources=[merged[lb] for lb in used],
                    previous_findings=previous,
                    notes=notes,
                    rec=rec,
                )
        except BudgetExceededError as exc:
            self.rep.event("budget.exhausted", str(exc))
            out.update(
                findings=previous,
                analysis_notes=state.get("analysis_notes", {}),
                analysis_failed=True,
                budget_exhausted=True,
                errors=[f"analysis: {exc}"],
            )
            return out
        except Exception as exc:
            log.exception("Fallo del Analysis Agent")
            out.update(
                findings=previous,
                analysis_notes=state.get("analysis_notes", {}),
                analysis_failed=True,
                errors=[f"analysis: {type(exc).__name__}: {exc}"[:400]],
            )
            return out
        findings = [
            {
                "id": f"F{i + 1}",
                "statement": f.statement,
                "kind": f.kind,
                "labels": f.evidence_labels,
                "aspect": f.aspect,
                "support": None,
                "note": "",
            }
            for i, f in enumerate(res.findings[: self.settings.max_findings])
        ]
        notes_out = {
            "agreements": res.agreements,
            "contradictions": [c.model_dump() for c in res.contradictions],
            "gaps": res.gaps,
            "preliminary_conclusions": res.preliminary_conclusions,
        }
        self.rep.event(
            "analysis.completed",
            f"{len(findings)} hallazgo(s)",
            {"gaps": len(res.gaps), "contradictions": len(res.contradictions)},
        )
        self.rep.sync_usage(self.tracker)
        out.update(
            findings=findings,
            analysis_notes=notes_out,
            messages=[
                _note(
                    "analysis",
                    f"{len(findings)} findings; gaps: {'; '.join(res.gaps)[:300]}",
                )
            ],
        )
        return out

    # ---- Verificación ----
    def verify(self, state: ResearchState) -> dict[str, Any]:
        self.rep.stage("verifying")
        try:
            with self.rep.execution(
                "verification", iteration=state.get("iteration", 1)
            ) as rec:
                findings, summary = self.verifier.verify(
                    findings=state.get("findings", []),
                    sources=state.get("sources", {}),
                    tasks=state["tasks"],
                    notes=state.get("analysis_notes", {}),
                    tracker=self.tracker,
                    rec=rec,
                )
        except Exception as exc:
            log.exception("Fallo del Verification Agent")
            return {
                "verification": {
                    "sufficient": False,
                    "coverage": 0.0,
                    "uncovered": [],
                    "contradictions": [],
                    "supported_facts": 0,
                    "total_facts": 0,
                },
                "errors": [f"verify: {type(exc).__name__}: {exc}"[:400]],
                "analysis_failed": True,
            }
        self.rep.event(
            "verification.completed",
            f"Cobertura {summary['coverage']:.0%}; {summary['supported_facts']}/{summary['total_facts']} hechos respaldados",
            summary,
        )
        self.rep.sync_usage(self.tracker)
        msg = f"coverage={summary['coverage']}; unsupported={summary['unsupported_ids']}; uncovered={[u['question'] for u in summary['uncovered']]}"
        return {
            "findings": findings,
            "verification": summary,
            "messages": [_note("verification", msg)],
        }

    # ---- Decisión del Supervisor ----
    def decide(self, state: ResearchState) -> dict[str, Any]:
        self.rep.stage("deciding")
        it = state.get("iteration", 1)
        with self.rep.execution("supervisor", iteration=it):
            decision = self.supervisor.decide(
                iteration=it,
                verification=state.get("verification", {}),
                analysis_notes=state.get("analysis_notes", {}),
                tasks=state.get("tasks", []),
                tracker=self.tracker,
                allow_reinvestigation=self.d.options.allow_reinvestigation,
            )
            if decision.action == "continue" and (
                state.get("budget_exhausted") or state.get("analysis_failed")
            ):
                from ars.schemas.agents import SupervisorDecision

                decision = SupervisorDecision(
                    action="finalize",
                    stop_reason="budget"
                    if state.get("budget_exhausted")
                    else "analysis_error",
                    reason="Fallo previo: no se reintenta.",
                )
        self.rep.event(
            "supervisor.decision",
            decision.reason,
            {"action": decision.action, "stop_reason": decision.stop_reason},
        )
        update: dict[str, Any] = {
            "decision": decision.model_dump(),
            "stop_reason": decision.stop_reason,
        }
        history = state.get("messages", [])
        update["messages"] = [
            _note(
                "supervisor", f"decision={decision.action}: {decision.reason}"
            )
        ] + prune_messages(history, self.settings.message_keep_last)
        if decision.action == "continue":
            new = [t.model_dump() for t in decision.new_tasks]
            update.update(tasks=new, pending=new, iteration=it + 1)
            self.rep.sync_usage(self.tracker, it + 1)
        return update

    def route_after_decide(self, state: ResearchState) -> list[Send] | str:
        if state.get("decision", {}).get("action") == "continue" and state.get(
            "pending"
        ):
            return self.fan_out(state)
        return "report"

    # ---- Informe ----
    def report(self, state: ResearchState) -> dict[str, Any]:
        self.rep.stage("reporting")
        analysis = state["analysis"]
        findings, sources, v = (
            state.get("findings", []),
            state.get("sources", {}),
            state.get("verification", {}),
        )
        results = state.get("task_results", [])
        stats = {
            "iterations": state.get("iteration", 1),
            "tasks": len(state.get("tasks", [])),
            "sources": len(sources),
            "strategies": sorted(
                {r["strategy"] for r in results if r.get("strategy")}
            ),
            "supported_facts": v.get("supported_facts", 0),
            "total_facts": v.get("total_facts", 0),
            "stop_reason": state.get("stop_reason", "n/d"),
        }
        limits = {
            "max_iterations": "Se alcanzó el máximo de iteraciones antes de cubrir todos los aspectos.",
            "budget": "Se agotó el presupuesto de tokens: la investigación puede estar incompleta.",
            "analysis_error": "El análisis falló en una iteración; la cobertura puede ser menor.",
            "no_new_tasks": "No se encontraron nuevas vías de búsqueda para los aspectos pendientes.",
        }
        extra = (
            [limits[state["stop_reason"]]]
            if state.get("stop_reason") in limits
            else []
        )
        extra += [
            f"Subtarea sin resultados por error: {r['task_id']}"
            for r in results
            if r.get("error")
        ]
        extra += [
            f"Contradicción entre fuentes: {c['topic']}"
            for c in v.get("contradictions", [])
        ][:3]
        try:
            with self.rep.execution("report") as rec:
                rep = self.reporter_agent.generate(
                    query=analysis["normalized_query"],
                    analysis=analysis,
                    findings=findings,
                    sources=sources,
                    notes=state.get("analysis_notes", {}),
                    verification=v,
                    stats=stats,
                    lang=analysis.get("language", "en"),
                    extra_limitations=extra,
                    rec=rec,
                )
        except Exception as exc:
            return self._fail(exc, "report")
        self.rep.event(
            "report.generated", rep["title"], {"degraded": rep["degraded"]}
        )
        self.rep.sync_usage(self.tracker)
        return {"report": rep}

    # ---- Evaluación final (determinista, sin LLM) ----
    def final_evaluation(self, state: ResearchState) -> dict[str, Any]:
        if state.get("failed"):
            return {}
        c = state["report"].get("content", {})
        v = state.get("verification", {})
        total, invalid = (
            c.get("citations_total", 0),
            c.get("citations_invalid", 0),
        )
        facts = v.get("total_facts", 0)
        quality = {
            "citation_validity": round(1 - invalid / total, 3)
            if total
            else 1.0,
            "evidence_coverage": v.get("coverage", 0.0),
            "supported_fact_ratio": round(
                v.get("supported_facts", 0) / facts, 3
            )
            if facts
            else 0.0,
            "iterations": state.get("iteration", 1),
            "stop_reason": state.get("stop_reason"),
            "degraded_report": state["report"].get("degraded", False),
        }
        self.rep.event(
            "research.completed", "Investigación completada", quality
        )
        self.rep.sync_usage(self.tracker)
        return {"quality": quality, "status": "completed"}
