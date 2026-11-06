"""Métricas deterministas de generación (aproximaciones léxicas, baratas y reproducibles).

Complementan —no sustituyen— a Ragas: miden solapamiento de términos, no comprensión semántica.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from ars.utils.text import content_tokens, split_sentences

_CITE = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")


def token_f1(prediction: str, reference: str) -> float:
    p, r = content_tokens(prediction), content_tokens(reference)
    if not p or not r:
        return 0.0
    common = sum(min(p.count(t), r.count(t)) for t in set(p) & set(r))
    if common == 0:
        return 0.0
    prec, rec = common / len(p), common / len(r)
    return 2 * prec * rec / (prec + rec)


def faithfulness_lexical(answer: str, contexts: Sequence[str], threshold: float = 0.5) -> float:
    """Fracción de oraciones de la respuesta cuyos términos aparecen mayoritariamente en el contexto."""
    vocab: set[str] = set()
    for c in contexts:
        vocab.update(content_tokens(c))
    sentences = [s for s in split_sentences(_CITE.sub("", answer)) if content_tokens(s)]
    if not sentences:
        return 0.0
    ok = 0
    for s in sentences:
        toks = set(content_tokens(s))
        ok += (len(toks & vocab) / len(toks)) >= threshold
    return ok / len(sentences)


def answer_relevancy_lexical(question: str, answer: str) -> float:
    q = set(content_tokens(question))
    return len(q & set(content_tokens(answer))) / len(q) if q else 0.0


def context_recall_lexical(reference: str, contexts: Sequence[str]) -> float:
    ref = set(content_tokens(reference))
    vocab: set[str] = set()
    for c in contexts:
        vocab.update(content_tokens(c))
    return len(ref & vocab) / len(ref) if ref else 0.0


def context_precision_doc(retrieved_docs: Sequence[str], relevant: set[str]) -> float:
    """Fracción de fragmentos recuperados que pertenecen a documentos relevantes."""
    return len([d for d in retrieved_docs if d in relevant]) / len(retrieved_docs) if retrieved_docs else 0.0


def citation_validity(answer: str, valid_labels: set[str]) -> tuple[int, int]:
    labels = [x.strip() for grp in _CITE.findall(answer) for x in grp.split(",")]
    return len([lb for lb in labels if lb in valid_labels]), len(labels)


def keyword_coverage(answer: str, keywords: Sequence[str]) -> float:
    if not keywords:
        return 1.0
    text = " ".join(content_tokens(answer))
    return len([k for k in keywords if " ".join(content_tokens(k)) in text]) / len(keywords)


def evaluate_generation(question: str, answer: str, contexts: Sequence[str], reference: str | None = None, valid_labels: set[str] | None = None) -> dict[str, float]:
    out = {"faithfulness_lexical": faithfulness_lexical(answer, contexts), "answer_relevancy_lexical": answer_relevancy_lexical(question, answer)}
    if reference:
        out["answer_correctness_f1"] = token_f1(answer, reference)
        out["context_recall_lexical"] = context_recall_lexical(reference, contexts)
    if valid_labels is not None:
        ok, total = citation_validity(answer, valid_labels)
        out["citation_accuracy"] = ok / total if total else 0.0
    return {k: round(v, 4) for k, v in out.items()}
