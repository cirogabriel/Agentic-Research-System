"""Query Routing: reglas deterministas primero; el LLM solo si está habilitado y las reglas no deciden."""
from __future__ import annotations

import re

from pydantic import BaseModel

from ars.config import Settings
from ars.llm.base import StructuredLLM
from ars.llm.budget import ExecutionRecord
from ars.schemas.rag import RoutingDecision, Strategy, Transform
from ars.utils.text import tokenize

_COMPARE = re.compile(r"\b(compar\w*|versus|vs\.?|diferenci\w*|differences?|contrast\w*|frente a|pros and cons|ventajas y desventajas)\b", re.I)
_SPECIFIC = re.compile(r'"[^"]+"|\b[A-Z]{2,}\b|\b\d{3,4}\b|\b\w+[-_/]\w+\b|\bM[w]?\s?\d')


class RouteChoice(BaseModel):
    strategy: Strategy
    transform: Transform
    reason: str


class QueryRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _rules(self, query: str) -> tuple[Strategy, Transform, str] | None:
        if _COMPARE.search(query):
            return "hybrid", "rag_fusion", "consulta comparativa: varias variantes de la consulta fusionadas con RRF"
        if len(tokenize(query)) <= 2:
            return "hybrid", "rewrite", "consulta muy corta: se reformula antes de buscar"
        if _SPECIFIC.search(query):
            return "hybrid", "none", "términos específicos (siglas, cifras, frases): la búsqueda léxica aporta precisión"
        return None

    def route(
        self,
        query: str,
        *,
        strategy: str = "auto",
        transform: str = "auto",
        llm: StructuredLLM | None = None,
        rec: ExecutionRecord | None = None,
    ) -> RoutingDecision:
        s = self.settings
        want_strategy = strategy if strategy != "auto" else s.retrieval_strategy
        want_transform = transform if transform != "auto" else s.query_transform
        decided = None if (want_strategy != "auto" and want_transform != "auto") else self._rules(query)
        used_llm, reason = False, "configuración explícita"

        if decided is None and (want_strategy == "auto" or want_transform == "auto"):
            if s.router_llm_fallback and llm is not None and not _COMPARE.search(query):
                choice = llm.structured(
                    RouteChoice,
                    system="Choose the cheapest retrieval strategy that will work. vector=semantic, keyword=exact terms, hybrid=both. "
                    "transform: none unless the query is ambiguous (rewrite) or multi-aspect (multi_query/rag_fusion).",
                    user=f"Query: {query}", rec=rec, max_tokens=150,
                )
                decided, used_llm = (choice.strategy, choice.transform, choice.reason), True
            else:
                decided = ("vector", "none", "consulta explicativa simple: búsqueda semántica (la más barata)")

        r_strategy, r_transform = (decided[0], decided[1]) if decided else ("hybrid", "none")
        if decided:
            reason = decided[2]
        final_strategy: Strategy = want_strategy if want_strategy != "auto" else r_strategy  # type: ignore[assignment]
        final_transform: Transform = want_transform if want_transform != "auto" else r_transform  # type: ignore[assignment]
        if final_transform == "hyde" and not s.hyde_enabled:  # HyDE es experimental: solo con HYDE_ENABLED=true
            final_transform, reason = "none", reason + " (HyDE desactivado por configuración)"
        return RoutingDecision(strategy=final_strategy, transform=final_transform, reason=reason, used_llm=used_llm)
