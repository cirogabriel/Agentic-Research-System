from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ars.schemas.rag import StrategyOrAuto, TransformOrAuto


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Investigaciones ----------------------------------------------------------------------------
class ResearchOptions(BaseModel):
    max_iterations: int | None = Field(None, ge=1, le=10)
    token_budget: int | None = Field(None, ge=2000, le=2_000_000)
    top_k: int | None = Field(None, ge=1, le=20)
    retrieval_strategy: StrategyOrAuto | None = None
    query_transform: TransformOrAuto | None = None
    document_ids: list[uuid.UUID] | None = None
    parallel: bool = True
    reinvestigate: bool = True


class ResearchCreate(BaseModel):
    query: str = Field(min_length=5, max_length=4000)
    options: ResearchOptions = Field(default_factory=ResearchOptions)
    parent_research_id: uuid.UUID | None = Field(
        None, description="Seguimiento de una investigación previa"
    )


class ClarificationIn(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)


class ResearchOut(ORMModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None = None
    query: str
    status: str
    current_stage: str | None = None
    stop_reason: str | None = None
    clarification_questions: list[str] | None = None
    iterations: int
    tokens_input: int
    tokens_output: int
    cost_usd: float
    created_at: datetime
    finished_at: datetime | None = None


class ResearchStatusOut(BaseModel):
    id: uuid.UUID
    status: str
    current_stage: str | None
    iteration: int
    tokens_input: int
    tokens_output: int
    embedding_tokens: int
    cost_usd: float
    clarification_questions: list[str] | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ResearchListOut(BaseModel):
    items: list[ResearchOut]
    total: int


class SourceOut(ORMModel):
    label: str
    document_id: uuid.UUID | None
    document_name: str
    page_number: int | None
    snippet: str
    score: float


class FindingOut(BaseModel):
    statement: str
    kind: str
    aspect: str | None
    support_level: str
    verification_note: str | None
    sources: list[str]


class ReportOut(BaseModel):
    research_id: uuid.UUID
    title: str
    markdown: str
    content: dict[str, Any]
    quality: dict[str, Any]
    sources: list[SourceOut]
    findings: list[FindingOut]
    created_at: datetime


class EventOut(ORMModel):
    id: int
    event_type: str
    message: str
    payload: dict[str, Any]
    created_at: datetime


# ---------------- Documentos --------------------------------------------------------------------------
class DocumentOut(ORMModel):
    id: uuid.UUID
    filename: str
    file_type: str
    title: str | None
    author: str | None
    document_date: datetime | None
    size_bytes: int
    content_hash: str
    version: int
    status: str
    error: str | None
    num_pages: int | None
    num_chunks: int
    created_at: datetime
    updated_at: datetime
    indexed_at: datetime | None


class DocumentUploadOut(BaseModel):
    document: DocumentOut
    action: Literal["created", "updated", "duplicate"]


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int


class ReindexOut(BaseModel):
    document: DocumentOut
    action: Literal["reindexing", "up_to_date"]


# --------- Evaluación ----------------------------------------------------------------------
class EvalItem(BaseModel):
    id: str
    question: str
    reference_answer: str | None = None
    relevant_documents: list[str] = Field(
        default_factory=list, description="Nombres de archivo relevantes"
    )
    expected_keywords: list[str] = Field(default_factory=list)
    expected_strategy: str | None = None
    expected_aspects: list[str] = Field(default_factory=list)


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    items: list[EvalItem] = Field(min_length=1)


class DatasetOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    items: list[dict[str, Any]]
    created_at: datetime


class EvaluationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    dataset_id: uuid.UUID
    mode: Literal["retrieval", "A", "B", "C"] = "retrieval"
    top_k: int = Field(5, ge=1, le=20)
    retrieval_strategy: StrategyOrAuto = "hybrid"
    rerank: bool | None = None
    use_ragas: bool = False
    max_iterations: int | None = Field(None, ge=1, le=10)
    token_budget: int | None = Field(None, ge=2000, le=2_000_000)


class EvaluationOut(ORMModel):
    id: uuid.UUID
    name: str
    dataset_id: uuid.UUID
    mode: str
    config: dict[str, Any]
    status: str
    summary: dict[str, Any] | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class EvaluationResultOut(ORMModel):
    item_id: str
    question: str
    answer: str | None
    status: str
    metrics: dict[str, Any]
    retrieved: list[str]
    latency_ms: int
    tokens_input: int
    tokens_output: int
    iterations: int
    error: str | None


class EvaluationDetailOut(EvaluationOut):
    results: list[EvaluationResultOut] = []


class EvaluationListOut(BaseModel):
    items: list[EvaluationOut]
    total: int


class ComparisonOut(BaseModel):
    baseline_id: uuid.UUID
    experiments: list[dict[str, Any]]
    deltas: dict[str, dict[str, float | None]]
