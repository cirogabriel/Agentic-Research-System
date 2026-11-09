
from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from ars.config import Settings
from ars.llm.base import StructuredLLM
from ars.llm.budget import ExecutionRecord
from ars.utils.text import normalize_whitespace


class _Rewrite(BaseModel):
    query: str


class _MultiQuery(BaseModel):
    queries: list[str] = Field(
        description="Consultas alternativas, distintas entre sí"
    )


class _Hyde(BaseModel):
    passage: str


@dataclass
class TransformResult:
    queries: list[str]
    hyde_passage: str | None = None
    llm_calls: int = 0
    notes: list[str] = field(default_factory=list)


class QueryTransformer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def expand(
        self,
        query: str,
        transform: str,
        llm: StructuredLLM | None,
        rec: ExecutionRecord | None = None,
    ) -> TransformResult:
        if transform == "none" or llm is None:
            return TransformResult([query])
        if transform == "rewrite":
            out = llm.structured(
                _Rewrite,
                rec=rec,
                max_tokens=120,
                system="Rewrite the search query so it is self-contained, precise and keyword-rich for document retrieval. "
                "Keep the original language and intent. Do not add assumptions or new facts.",
                user=query,
            )
            return TransformResult(
                [normalize_whitespace(out.query) or query], llm_calls=1
            )
        if transform in {"multi_query", "rag_fusion"}:
            n = self.settings.multi_query_count
            out = llm.structured(
                _MultiQuery,
                rec=rec,
                max_tokens=250,
                system=f"Generate {n} alternative search queries for the user's question, each covering a different wording or aspect. "
                "Keep the original language. Do not add assumptions.",
                user=query,
            )
            variants = [query] + [q.strip() for q in out.queries if q.strip()]
            unique = list(dict.fromkeys(variants))[: n + 1]
            return TransformResult(unique, llm_calls=1)
        if transform == "hyde":
            out = llm.structured(
                _Hyde,
                rec=rec,
                max_tokens=220,
                system="Write a short (max 100 words) factual-sounding passage that would answer the question. "
                "It is used ONLY as a search probe, never shown to the user.",
                user=query,
            )
            return TransformResult(
                [query], hyde_passage=out.passage, llm_calls=1
            )
        return TransformResult([query])
