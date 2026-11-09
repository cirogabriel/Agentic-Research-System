from __future__ import annotations

from typing import Any

from ars.agents import prompts
from ars.config import Settings
from ars.llm.base import StructuredLLM
from ars.llm.budget import ExecutionRecord
from ars.schemas.agents import AnalysisOutput
from ars.schemas.query import QueryAnalysis
from ars.security import wrap_untrusted


class AnalysisAgent:
    def __init__(self, llm: StructuredLLM, settings: Settings) -> None:
        self.llm, self.settings = llm, settings

    def analyze(
        self,
        *,
        analysis: QueryAnalysis,
        tasks: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        previous_findings: list[dict[str, Any]],
        notes: str = "",
        rec: ExecutionRecord | None = None,
    ) -> AnalysisOutput:
        plan = "\n".join(
            f"- {t['id']}: {t['title']} — {t['question']}" for t in tasks
        )
        evidence = "\n".join(
            wrap_untrusted(
                s["label"],
                s["text"],
                source=f"{s['document_name']}"
                + (f" p.{s['page_number']}" if s.get("page_number") else ""),
            )
            for s in sources
        )
        prev = "\n".join(
            f"{f['id']} [{', '.join(f['labels'])}] ({f['kind']}, {f.get('support') or 'unchecked'}): {f['statement']}"
            for f in previous_findings
        )
        user = (
            f"<question>{analysis.normalized_query}</question>\n<plan>\n{plan}\n</plan>\n"
            + (
                f"<previous_findings>\n{prev}\n</previous_findings>\n"
                if prev
                else ""
            )
            + (f"<team_notes>\n{notes}\n</team_notes>\n" if notes else "")
            + f"<context>\n{evidence or '(no evidence retrieved)'}\n</context>"
        )
        system = prompts.ANALYSIS.format(
            max_findings=self.settings.max_findings
        )
        return self.llm.structured(
            AnalysisOutput, system=system, user=user, rec=rec
        )
