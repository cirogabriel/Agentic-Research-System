import math

from ars.evaluation import agent_metrics as am
from ars.evaluation import generation_metrics as gm
from ars.evaluation import retrieval_metrics as rm
from ars.evaluation.experiments import flatten


def test_retrieval_metrics_known_values():
    ranked, relevant = ["d1", "d2", "d3", "d4"], {"d2", "d4", "d9"}
    assert rm.recall_at_k(ranked, relevant, 2) == 1 / 3
    assert rm.precision_at_k(ranked, relevant, 4) == 0.5
    assert rm.reciprocal_rank(ranked, relevant) == 0.5
    expected = (1 / math.log2(3) + 1 / math.log2(5)) / (
        1 + 1 / math.log2(3) + 1 / math.log2(4)
    )
    assert abs(rm.ndcg_at_k(ranked, relevant, 4) - expected) < 1e-9
    assert (
        rm.reciprocal_rank(["x"], relevant) == 0.0
        and rm.recall_at_k([], set(), 3) == 0.0
    )
    assert rm.dedupe_ranking(["a", "b", "a", "c"]) == ["a", "b", "c"]


def test_mean_metrics():
    assert rm.mean_metrics([{"mrr": 1.0}, {"mrr": 0.0}]) == {"mrr": 0.5}


def test_generation_metrics_are_deterministic():
    ctx = [
        "La placa de Nazca subduce bajo la placa Sudamericana a 7 cm por año."
    ]
    assert (
        gm.faithfulness_lexical(
            "La placa de Nazca subduce bajo Sudamérica. Los volcanes de Marte son enormes.",
            ctx,
        )
        == 0.5
    )
    assert (
        gm.token_f1("placa de Nazca", "placa de Nazca") == 1.0
        and gm.token_f1("abc", "xyz") == 0.0
    )
    assert gm.citation_validity(
        "Hecho [S1, S9] y otro [S2].", {"S1", "S2"}
    ) == (2, 3)
    assert (
        gm.keyword_coverage(
            "Nazca y Sudamericana", ["nazca", "sudamericana", "caribe"]
        )
        == 2 / 3
    )
    out = gm.evaluate_generation(
        "¿Qué placas?", "La placa de Nazca [S1]", ctx, "placa de Nazca", {"S1"}
    )
    assert (
        out["citation_accuracy"] == 1.0 and out["answer_correctness_f1"] > 0.5
    )


def _outcome(**kw):
    base = dict(
        item_id="1",
        status="completed",
        answer="Nazca y Sudamericana",
        latency_ms=100,
        tokens_in=10,
        tokens_out=5,
    )
    base.update(kw)
    return am.RunOutcome(**base)


def test_agent_metrics():
    ok = _outcome(
        expected_keywords=["Nazca"],
        citations_ok=2,
        citations_total=2,
        expected_strategy="hybrid",
        strategies=["hybrid"],
        tasks=[{"title": "Placas", "question": "¿Qué placas intervienen?"}],
        expected_aspects=["placas", "volcanes"],
        executions=[{"status": "completed"}, {"status": "failed"}],
        evidence_coverage=1.0,
        iterations=2,
    )
    bad = _outcome(
        item_id="2",
        status="failed",
        answer="",
        latency_ms=300,
        citations_ok=0,
        citations_total=2,
        expected_strategy="vector",
        strategies=["hybrid"],
    )
    s = am.summarize([ok, bad])
    assert (
        s["task_completion_rate"] == 0.5
        and s["citation_accuracy"] == 0.5
        and s["tool_selection_accuracy"] == 0.5
    )
    assert (
        s["delegation_accuracy"] == 0.5
        and s["agent_failure_rate"] == 0.5
        and s["iterations_per_task"] == 1.5
    )
    assert s["tokens_per_task"] == 15 and s["latency_ms_p95"] == 300.0


def test_flatten():
    assert flatten({"retrieval": {"mrr": 1, "x": "s"}, "meta": {"n": 2}}) == {
        "retrieval.mrr": 1.0,
        "meta.n": 2.0,
    }
