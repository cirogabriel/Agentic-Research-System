from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from ars.evaluation.generation_metrics import keyword_coverage
from ars.utils.text import content_tokens


@dataclass
class RunOutcome:
    item_id: str
    status: str
    answer: str
    latency_ms: int
    tokens_in: int = 0
    tokens_out: int = 0
    iterations: int = 1
    executions: list[dict[str, Any]] = field(
        default_factory=list
    )  # {agent, status, tool_calls}
    tasks: list[dict[str, Any]] = field(
        default_factory=list
    )  # {title, question}
    strategies: list[str] = field(default_factory=list)
    citations_ok: int = 0
    citations_total: int = 0
    evidence_coverage: float = 0.0
    expected_keywords: list[str] = field(default_factory=list)
    expected_strategy: str | None = None
    expected_aspects: list[str] = field(default_factory=list)


def _mean(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 4) if xs else 0.0


def task_completion_rate(outcomes: list[RunOutcome]) -> float:
    return _mean(
        [
            float(
                o.status == "completed"
                and bool(o.answer.strip())
                and keyword_coverage(o.answer, o.expected_keywords) >= 0.5
            )
            for o in outcomes
        ]
    )


def tool_selection_accuracy(outcomes: list[RunOutcome]) -> float | None:
    rated = [o for o in outcomes if o.expected_strategy]
    if not rated:
        return None
    return _mean([float(o.expected_strategy in o.strategies) for o in rated])


def delegation_accuracy(outcomes: list[RunOutcome]) -> float | None:
    scores = []
    for o in outcomes:
        if not o.expected_aspects:
            continue
        task_vocab = {
            t
            for task in o.tasks
            for t in content_tokens(
                f"{task.get('title', '')} {task.get('question', '')}"
            )
        }
        hits = [
            bool(set(content_tokens(a)) & task_vocab)
            for a in o.expected_aspects
        ]
        scores.append(sum(hits) / len(hits))
    return _mean(scores) if scores else None


def citation_accuracy(outcomes: list[RunOutcome]) -> float:
    total = sum(o.citations_total for o in outcomes)
    return (
        round(sum(o.citations_ok for o in outcomes) / total, 4)
        if total
        else 0.0
    )


def agent_failure_rate(outcomes: list[RunOutcome]) -> float:
    execs = [e for o in outcomes for e in o.executions]
    return (
        round(
            len([e for e in execs if e.get("status") == "failed"]) / len(execs),
            4,
        )
        if execs
        else 0.0
    )


def _pct(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(
        ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]
    )


def summarize(outcomes: list[RunOutcome]) -> dict[str, Any]:
    lat = [o.latency_ms for o in outcomes]
    out: dict[str, Any] = {
        "items": len(outcomes),
        "task_completion_rate": task_completion_rate(outcomes),
        "citation_accuracy": citation_accuracy(outcomes),
        "evidence_coverage": _mean([o.evidence_coverage for o in outcomes]),
        "iterations_per_task": _mean([float(o.iterations) for o in outcomes]),
        "agent_failure_rate": agent_failure_rate(outcomes),
        "tokens_per_task": _mean(
            [float(o.tokens_in + o.tokens_out) for o in outcomes]
        ),
        "tokens_input_total": sum(o.tokens_in for o in outcomes),
        "tokens_output_total": sum(o.tokens_out for o in outcomes),
        "latency_ms_mean": _mean([float(x) for x in lat]),
        "latency_ms_p50": float(statistics.median(lat)) if lat else 0.0,
        "latency_ms_p95": _pct(lat, 0.95),
    }
    for name, val in (
        ("tool_selection_accuracy", tool_selection_accuracy(outcomes)),
        ("delegation_accuracy", delegation_accuracy(outcomes)),
    ):
        if val is not None:
            out[name] = val
    return out
