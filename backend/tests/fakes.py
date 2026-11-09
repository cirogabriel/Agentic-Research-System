"""Dobles de prueba: ningún test consume la API de OpenAI ni necesita PostgreSQL """

from __future__ import annotations

import hashlib
import math
import uuid
from collections.abc import Callable
from typing import Any

from ars.exceptions import LLMError
from ars.llm.budget import ExecutionRecord, UsageTracker
from ars.schemas.rag import (
    RetrievalRequest,
    RetrievalResult,
    RoutingDecision,
    ScoredChunk,
)
from ars.utils.text import content_tokens


class FakeLLM:
   

    def __init__(
        self, tracker: UsageTracker, responses: dict[type, Any] | None = None
    ) -> None:
        self.tracker = tracker
        self.responses = responses or {}
        self.calls: list[tuple[str, str]] = []

    def structured(
        self,
        schema: type,
        *,
        system: str,
        user: str,
        rec: ExecutionRecord | None = None,
        max_tokens: int | None = None,
        use_reserve: bool = False,
    ) -> Any:
        self.tracker.check(use_reserve=use_reserve)
        self.calls.append((schema.__name__, user))
        self.tracker.charge(100, 50)
        if rec is not None:
            rec.tokens_in += 100
            rec.tokens_out += 50
            rec.llm_calls += 1
        if schema not in self.responses:
            raise LLMError(f"FakeLLM sin respuesta para {schema.__name__}")
        value = self.responses[schema]
        if isinstance(value, list):
            return value.pop(0) if len(value) > 1 else value[0]
        return value(user) if callable(value) else value

    def count(self, schema_name: str) -> int:
        return len([c for c in self.calls if c[0] == schema_name])


class FakeToolbox:


    def __init__(self, corpus: dict[str, str]) -> None:
        self.chunks = [
            ScoredChunk(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                document_name=name,
                chunk_index=0,
                content=text,
                score=0.0,
            )
            for name, text in corpus.items()
        ]
        self.requests: list[RetrievalRequest] = []

    def retrieve(
        self, req: RetrievalRequest, rec: ExecutionRecord | None = None
    ) -> RetrievalResult:
        self.requests.append(req)
        q = set(content_tokens(req.query))
        scored = []
        for c in self.chunks:
            overlap = len(q & set(content_tokens(c.content)))
            if overlap:
                scored.append(c.model_copy(update={"score": float(overlap)}))
        scored.sort(key=lambda c: -c.score)
        if rec is not None:
            rec.tool_calls.append("hybrid_search")
        return RetrievalResult(
            chunks=scored[: req.top_k],
            decision=RoutingDecision(
                strategy=("hybrid" if req.strategy == "auto" else req.strategy),
                transform="none",
                reason="fake",
            ),
            queries=[req.query],
            latency_ms=1,
        )


class FakeEmbeddingClient:
  

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.calls = 0

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in content_tokens(text):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def make_resolver(fn: Callable[[str], Any]) -> Callable[[str], Any]:
    return fn
