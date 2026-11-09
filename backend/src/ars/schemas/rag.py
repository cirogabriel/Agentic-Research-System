
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Strategy = Literal["vector", "keyword", "hybrid"]
StrategyOrAuto = Literal["auto", "vector", "keyword", "hybrid"]
Transform = Literal["none", "rewrite", "multi_query", "rag_fusion", "hyde"]
TransformOrAuto = Literal[
    "auto", "none", "rewrite", "multi_query", "rag_fusion", "hyde"
]


class SearchFilters(BaseModel):
    document_ids: list[uuid.UUID] | None = None
    file_types: list[str] | None = None
    author: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class ScoredChunk(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page_number: int | None = None
    chunk_index: int
    content: str
    score: float
    source: str = "vector"  # vector | keyword | fused | rerank
    rerank_score: float | None = None


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    strategy: StrategyOrAuto = "auto"
    transform: TransformOrAuto = "auto"
    top_k: int = Field(5, ge=1, le=50)
    rerank: bool | None = None  # None = usar la configuración global
    filters: SearchFilters | None = None


class RoutingDecision(BaseModel):
    strategy: Strategy
    transform: Transform
    reason: str
    used_llm: bool = False


class RetrievalResult(BaseModel):
    chunks: list[ScoredChunk]
    decision: RoutingDecision
    queries: list[str]
    latency_ms: int
    cache_hit: bool = False
    llm_calls: int = 0
    reranked: bool = False
