"""Verification Agent: comprueba que cada afirmación esté respaldada por los fragmentos citados.

Diseño híbrido para ahorrar tokens: primero comprobaciones deterministas (etiquetas válidas, solapamiento léxico) y
solo los hallazgos dudosos se envían al LLM en UNA llamada por lotes. Nunca se da por respaldada una afirmación
cuyo texto citado no la contiene.
"""
from __future__ import annotations

import logging
from typing import Any

from ars.agents import prompts
from ars.config import Settings
from ars.enums import Support
from ars.exceptions import ARSError
from ars.llm.base import StructuredLLM
from ars.llm.budget import ExecutionRecord, UsageTracker
from ars.schemas.agents import VerificationVerdicts
from ars.security import wrap_untrusted
from ars.utils.text import content_tokens

log = logging.getLogger(__name__)
PARTIAL_FLOOR = 0.3


def support_score(statement: str, evidence_texts: list[str]) -> float:
    """Fracción de términos de contenido de la afirmación que aparecen en las evidencias citadas (0..1)."""
    claim = set(content_tokens(statement))
    if not claim:
        return 0.0
    vocab: set[str] = set()
    for t in evidence_texts:
        vocab.update(content_tokens(t))
    return len(claim & vocab) / len(claim)


class VerificationAgent:
    def __init__(self, llm: StructuredLLM, settings: Settings, use_llm: bool = True) -> None:
        self.llm, self.settings, self.use_llm = llm, settings, use_llm

    def verify(self, *, findings: list[dict[str, Any]], sources: dict[str, dict[str, Any]], tasks: list[dict[str, Any]],
               notes: dict[str, Any], tracker: UsageTracker, rec: ExecutionRecord | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        s = self.settings
        out = [dict(f) for f in findings]
        pending: list[dict[str, Any]] = []
        for f in out:
            f["labels"] = [lb for lb in dict.fromkeys(f.get("labels", [])) if lb in sources]  # referencias inexistentes se descartan
            if f.get("kind") == "interpretation":
                f["support"], f["note"] = Support.UNVERIFIED.value, "Interpretación: no es una afirmación literal de las fuentes."
                continue
            if not f["labels"]:
                f["support"], f["note"] = Support.UNSUPPORTED.value, "Sin evidencia citada válida."
                continue
            f["score"] = round(support_score(f["statement"], [sources[lb]["text"] for lb in f["labels"]]), 3)
            if s.verification_mode != "llm" and f["score"] >= s.verification_support_threshold:
                f["support"], f["note"] = Support.SUPPORTED.value, f"Verificación léxica ({f['score']})."
            else:
                pending.append(f)

        llm_checked = 0
        if pending and self.use_llm and s.verification_mode != "lexical":
            batch, overflow = pending[: s.verification_max_llm_findings], pending[s.verification_max_llm_findings:]
            try:
                llm_checked = self._llm_verdicts(batch, sources, rec)
            except ARSError as exc:  # presupuesto agotado o fallo del LLM: se degrada a criterios léxicos
                log.warning("Verificación con LLM no disponible: %s", exc)
            pending = [f for f in batch if "support" not in f] + overflow
        for f in pending:  # lo que no pasó por el LLM se resuelve por puntuación léxica
            if f["score"] >= PARTIAL_FLOOR:
                f["support"], f["note"] = Support.PARTIAL.value, f"Respaldo léxico parcial ({f['score']}); no verificado por LLM."
            else:
                f["support"], f["note"] = Support.UNSUPPORTED.value, f"Poco solapamiento con la evidencia citada ({f['score']})."

        return out, self._summarize(out, sources, tasks, notes, llm_checked)

    def _llm_verdicts(self, batch: list[dict[str, Any]], sources: dict[str, dict[str, Any]], rec: ExecutionRecord | None) -> int:
        blocks = []
        for f in batch:
            cited = "\n".join(wrap_untrusted(lb, sources[lb]["text"], max_chars=900) for lb in f["labels"])
            blocks.append(f"<finding id=\"{f['id']}\">{f['statement']}</finding>\n{cited}")
        res = self.llm.structured(VerificationVerdicts, system=prompts.VERIFICATION, user="\n\n".join(blocks), rec=rec, max_tokens=700)
        by_id = {v.id: v for v in res.verdicts}
        for f in batch:
            v = by_id.get(f["id"])
            if v is not None:
                f["support"], f["note"] = Support(v.verdict).value, (v.note or "")[:300]
        return len(batch)

    def _summarize(self, findings: list[dict[str, Any]], sources: dict[str, dict[str, Any]], tasks: list[dict[str, Any]],
                   notes: dict[str, Any], llm_checked: int) -> dict[str, Any]:
        s = self.settings
        facts = [f for f in findings if f.get("kind") != "interpretation"]
        supported = [f for f in facts if f.get("support") == Support.SUPPORTED.value]
        bad = [f for f in facts if f.get("support") in (Support.UNSUPPORTED.value, Support.CONTRADICTED.value)]
        covered: set[str] = set()
        for f in supported:
            for lb in f["labels"]:
                covered.update(sources[lb].get("task_ids", []))
        replaced = {t.get("replaces") for t in tasks if t.get("replaces")}
        active = [t for t in tasks if t["id"] not in replaced]  # un reintento sustituye a la subtarea original
        task_ids = [t["id"] for t in active]
        coverage = round(len([t for t in task_ids if t in covered]) / len(task_ids), 3) if task_ids else 0.0
        ratio = round(len(bad) / len(facts), 3) if facts else 1.0
        sufficient = bool(supported) and coverage >= s.min_evidence_coverage and ratio <= s.max_unsupported_ratio
        contradictions = list(notes.get("contradictions", [])) + [{"topic": f["statement"], "positions": [f.get("note", "")], "evidence_labels": f["labels"]}
                                                                  for f in facts if f.get("support") == Support.CONTRADICTED.value]
        return {
            "sufficient": sufficient, "coverage": coverage, "unsupported_ratio": ratio, "supported_facts": len(supported), "total_facts": len(facts),
            "unsupported_ids": [f["id"] for f in bad], "uncovered": [{"id": t["id"], "question": t["question"]} for t in active if t["id"] not in covered],
            "contradictions": contradictions, "llm_checked": llm_checked,
        }
