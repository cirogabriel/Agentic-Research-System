"""Report Agent: el LLM redacta la narrativa; las referencias, la clasificación y la metodología las genera el código."""
from __future__ import annotations

import logging
from typing import Any

from ars.agents import prompts
from ars.agents.report_render import render_fallback, render_markdown
from ars.exceptions import ARSError
from ars.llm.base import StructuredLLM
from ars.llm.budget import ExecutionRecord
from ars.schemas.agents import ReportDraft

log = logging.getLogger(__name__)


class ReportAgent:
    def __init__(self, llm: StructuredLLM) -> None:
        self.llm = llm

    def generate(self, *, query: str, analysis: dict[str, Any], findings: list[dict[str, Any]], sources: dict[str, dict[str, Any]],
                 notes: dict[str, Any], verification: dict[str, Any], stats: dict[str, Any], lang: str, extra_limitations: list[str],
                 rec: ExecutionRecord | None = None) -> dict[str, Any]:
        used = sorted({lb for f in findings for lb in f.get("labels", [])}, key=lambda x: int(x[1:]))
        fl = "\n".join(f"{f['id']} [{', '.join(f['labels'])}] kind={f['kind']} support={f.get('support')}: {f['statement']}" for f in findings)
        refs = "\n".join(f"{lb}: {sources[lb]['document_name']}" + (f" p.{sources[lb]['page_number']}" if sources[lb].get("page_number") else "") for lb in used)
        contradictions = "\n".join(f"- {c['topic']}: {' | '.join(c['positions'])} [{', '.join(c.get('evidence_labels', []))}]" for c in verification.get("contradictions", []))
        user = (f"<question>{analysis['normalized_query']}</question>\nObjective: {analysis['objective']}\n<findings>\n{fl or '(none)'}\n</findings>\n"
                f"<sources>\n{refs or '(none)'}\n</sources>\nContradictions:\n{contradictions or 'none'}\nGaps: {'; '.join(notes.get('gaps', [])) or 'none'}\n"
                f"Known limitations: {'; '.join(extra_limitations) or 'none'}")
        try:
            draft = self.llm.structured(ReportDraft, system=prompts.REPORT, user=user, rec=rec, max_tokens=1500, use_reserve=True)
            degraded = False
        except ARSError as exc:  # sin LLM disponible siempre se entrega algo verificable
            log.warning("Redacción del informe con LLM falló (%s); se usa informe determinista", exc)
            draft = render_fallback(query=query, findings=findings, sources=sources, notes=notes, stats=stats, lang=lang, reason=str(exc)[:200])
            extra_limitations = extra_limitations + [f"Informe generado sin redacción por LLM: {str(exc)[:120]}"]
            degraded = True
        markdown, cite_stats = render_markdown(draft, findings=findings, sources=sources, stats=stats, lang=lang, extra_limitations=extra_limitations)
        return {"title": draft.title, "markdown": markdown, "summary": draft.executive_summary, "degraded": degraded,
                "content": {**draft.model_dump(), **cite_stats}}
