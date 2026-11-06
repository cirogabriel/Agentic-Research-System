"""Selección y etiquetado determinista de evidencias (sin LLM): S1, S2, ... compartidas por todos los agentes."""
from __future__ import annotations

from typing import Any

from ars.utils.text import truncate_chars


def select_evidence(
    task_results: list[dict[str, Any]],
    existing: dict[str, dict[str, Any]],
    *,
    per_task: int,
    max_chars: int,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Reparte el presupuesto de caracteres entre tareas (round-robin por orden de relevancia).

    Devuelve (fuentes_nuevas_o_actualizadas, etiquetas_usadas_en_esta_iteración). Un fragmento ya visto reutiliza su etiqueta.
    """
    by_chunk = {s["chunk_id"]: label for label, s in existing.items()}
    update: dict[str, dict[str, Any]] = {}
    used: list[str] = []
    next_n = len(existing) + 1
    queues = [list(r["evidence"][:per_task]) for r in task_results]
    task_ids = [r["task_id"] for r in task_results]
    budget = max_chars
    progressed = True
    while progressed and budget > 0:
        progressed = False
        for qi, queue in enumerate(queues):
            if not queue or budget <= 0:
                continue
            ev = queue.pop(0)
            progressed = True
            text = truncate_chars(ev["text"], budget)
            budget -= len(text)
            label = by_chunk.get(ev["chunk_id"])
            if label is None:
                label = f"S{next_n}"
                next_n += 1
                by_chunk[ev["chunk_id"]] = label
                update[label] = {
                    "label": label, "chunk_id": ev["chunk_id"], "document_id": ev["document_id"], "document_name": ev["document_name"],
                    "page_number": ev.get("page_number"), "chunk_index": ev.get("chunk_index", 0), "text": ev["text"],
                    "score": ev["score"], "task_ids": [task_ids[qi]],
                }
            else:
                prev = update.get(label) or {**existing[label], "task_ids": []}
                update[label] = {**prev, "task_ids": sorted(set(prev["task_ids"]) | {task_ids[qi]}), "score": max(prev["score"], ev["score"])}
            if label not in used:
                used.append(label)
    return update, used


def merge_sources(left: dict[str, dict[str, Any]] | None, right: dict[str, dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """Reducer de LangGraph para el diccionario de fuentes: une task_ids y conserva la mejor puntuación."""
    merged = dict(left or {})
    for label, src in (right or {}).items():
        if label in merged:
            old = merged[label]
            merged[label] = {**old, **src, "task_ids": sorted(set(old.get("task_ids", [])) | set(src.get("task_ids", []))),
                             "score": max(old.get("score", 0.0), src.get("score", 0.0))}
        else:
            merged[label] = src
    return merged
