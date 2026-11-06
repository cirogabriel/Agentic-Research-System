"""Servicio de evaluación sin base de datos: contenedor simulado con recuperación en memoria y LLM falso."""
from types import SimpleNamespace

from fakes import FakeLLM, FakeToolbox

from ars.evaluation.experiments import ExperimentRunner
from ars.rag.cache import TTLCache
from ars.schemas.agents import BaselineAnswer

ITEM = {"id": "q1", "question": "¿Qué placas tectónicas intervienen en los terremotos de los Andes?",
        "reference_answer": "La placa de Nazca subduce bajo la placa Sudamericana.", "relevant_documents": ["andes_subduction.md"],
        "expected_keywords": ["Nazca"], "expected_strategy": "hybrid"}


def make_container(settings, tracker_factory, corpus, answer):
    toolbox = FakeToolbox(corpus)
    retrieval = SimpleNamespace(cache=TTLCache(8, 60), retrieve=lambda req, **kw: toolbox.retrieve(req))
    return SimpleNamespace(settings=settings, retrieval=retrieval, new_tracker=lambda budget=None: tracker_factory(),
                           new_llm=lambda tr: FakeLLM(tr, {BaselineAnswer: BaselineAnswer(answer=answer)}))


def test_retrieval_item_metrics_and_summary(settings, tracker, corpus):
    runner = ExperimentRunner(make_container(settings, lambda: tracker, corpus, ""))
    res = runner.run_retrieval_item(ITEM, {"retrieval_strategy": "hybrid"})
    assert res["retrieved"] == ["andes_subduction.md"] and res["metrics"]["mrr"] == 1.0 and res["metrics"]["recall@1"] == 1.0
    summary = runner.summarize("retrieval", [{**res, "status": "completed"}])
    assert summary["retrieval"]["mrr"] == 1.0 and "agent" not in summary and summary["meta"]["items_failed"] == 0


def test_baseline_item_full_metrics(settings, tracker, corpus):
    runner = ExperimentRunner(make_container(settings, lambda: tracker, corpus, "La placa de Nazca subduce bajo la placa Sudamericana [S1]."))
    res = runner.run_baseline_item(ITEM, {"top_k": 3})
    m = res["metrics"]
    assert res["status"] == "completed" and (res["tokens_in"], res["tokens_out"]) == (100, 50)
    assert m["citation_accuracy"] == 1.0 and m["recall@1"] == 1.0 and m["answer_correctness_f1"] > 0.8 and m["faithfulness_lexical"] == 1.0
    summary = runner.summarize("A", [res])
    assert summary["agent"]["task_completion_rate"] == 1.0 and summary["agent"]["tool_selection_accuracy"] == 1.0
    assert summary["cost"]["tokens_total"] == 150 and summary["cost"]["cost_usd_total"] > 0


def test_baseline_item_survives_llm_failure(settings, tracker, corpus):
    c = make_container(settings, lambda: tracker, corpus, "")
    c.new_llm = lambda tr: FakeLLM(tr, {})  # sin respuesta configurada → LLMError
    res = ExperimentRunner(c).run_baseline_item(ITEM, {})
    assert res["status"] == "failed" and res["answer"] == ""
