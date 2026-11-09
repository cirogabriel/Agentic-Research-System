from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def dedupe_ranking(doc_names: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(doc_names))


def recall_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    return len(set(ranked[:k]) & relevant) / len(relevant) if relevant else 0.0


def precision_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    return len([d for d in ranked[:k] if d in relevant]) / k if k > 0 else 0.0


def reciprocal_rank(ranked: Sequence[str], relevant: set[str]) -> float:
    for i, d in enumerate(ranked, start=1):
        if d in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    dcg = sum(
        1.0 / math.log2(i + 1)
        for i, d in enumerate(ranked[:k], start=1)
        if d in relevant
    )
    ideal = sum(
        1.0 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1)
    )
    return dcg / ideal if ideal else 0.0


def evaluate_ranking(
    ranked: Sequence[str], relevant: set[str], ks: Sequence[int] = (1, 3, 5)
) -> dict[str, float]:
    out: dict[str, float] = {"mrr": reciprocal_rank(ranked, relevant)}
    for k in ks:
        out[f"recall@{k}"] = recall_at_k(ranked, relevant, k)
        out[f"precision@{k}"] = precision_at_k(ranked, relevant, k)
        out[f"ndcg@{k}"] = ndcg_at_k(ranked, relevant, k)
    return out


def mean_metrics(rows: Sequence[dict[str, float]]) -> dict[str, float]:
    keys = {k for r in rows for k in r}
    return {
        k: round(
            sum(r[k] for r in rows if k in r)
            / max(1, len([r for r in rows if k in r])),
            4,
        )
        for k in sorted(keys)
    }
