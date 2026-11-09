from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Column,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ars.config import get_settings
from ars.db.base import Base

EMBED_DIM = get_settings().embedding_dimensions
TS = DateTime(timezone=True)


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(TS, server_default=func.now(), nullable=False)


# -------Documentos / RAG
class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("filename", name="uq_documents_filename"),
        UniqueConstraint("content_hash", name="uq_documents_content_hash"),
        Index("ix_documents_status", "status"),
    )

    id: Mapped[uuid.UUID] = _pk()
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str | None] = mapped_column(String(512))
    author: Mapped[str | None] = mapped_column(String(256))
    document_date: Mapped[datetime | None] = mapped_column(TS)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    content_hash: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(1024))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="processing")
    error: Mapped[str | None] = mapped_column(Text)
    num_pages: Mapped[int | None] = mapped_column(Integer)
    num_chunks: Mapped[int] = mapped_column(Integer, default=0)
    index_signature: Mapped[str | None] = mapped_column(String(64))
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    indexed_at: Mapped[datetime | None] = mapped_column(TS)

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_chunks_document_index"
        ),
        Index("ix_chunks_document_id", "document_id"),
        Index(
            "ix_chunks_search_vector", "search_vector", postgresql_using="gin"
        ),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)
    token_estimate: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[Any] = mapped_column(Vector(EMBED_DIM))
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', content)", persisted=True)
    )
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()

    document: Mapped[Document] = relationship(back_populates="chunks")


class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"

    content_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(64), primary_key=True)
    dimensions: Mapped[int] = mapped_column(Integer, primary_key=True)
    embedding: Mapped[Any] = mapped_column(Vector(EMBED_DIM))
    created_at: Mapped[datetime] = _created()


# ----------------- Investigaciones
finding_sources = Table(
    "finding_sources",
    Base.metadata,
    Column(
        "finding_id",
        Uuid,
        ForeignKey("research_findings.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "source_id",
        Uuid,
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ResearchSession(Base):
    __tablename__ = "research_sessions"
    __table_args__ = (
        Index("ix_research_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = _pk()
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("research_sessions.id", ondelete="SET NULL")
    )
    query: Mapped[str] = mapped_column(Text)
    normalized: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    current_stage: Mapped[str | None] = mapped_column(String(48))
    stop_reason: Mapped[str | None] = mapped_column(String(32))
    clarification_questions: Mapped[list[str] | None] = mapped_column(JSONB)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    embedding_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    started_at: Mapped[datetime | None] = mapped_column(TS)
    finished_at: Mapped[datetime | None] = mapped_column(TS)

    tasks: Mapped[list[ResearchTask]] = relationship(
        back_populates="research",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    executions: Mapped[list[AgentExecution]] = relationship(
        back_populates="research",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    findings: Mapped[list[ResearchFinding]] = relationship(
        back_populates="research",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sources: Mapped[list[Source]] = relationship(
        back_populates="research",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    report: Mapped[Report | None] = relationship(
        back_populates="research",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    events: Mapped[list[ResearchEvent]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    messages: Mapped[list[ResearchMessage]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class ResearchTask(Base):
    __tablename__ = "research_tasks"
    __table_args__ = (
        UniqueConstraint("research_id", "key", name="uq_tasks_research_key"),
    )

    id: Mapped[uuid.UUID] = _pk()
    research_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_sessions.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(32))
    iteration: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(256))
    question: Mapped[str] = mapped_column(Text)
    aspect: Mapped[str | None] = mapped_column(String(256))
    strategy_hint: Mapped[str] = mapped_column(String(16), default="auto")
    strategy_used: Mapped[str | None] = mapped_column(String(16))
    transform_used: Mapped[str | None] = mapped_column(String(16))
    queries_used: Mapped[list[str]] = mapped_column(JSONB, default=list)
    num_evidence: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()

    research: Mapped[ResearchSession] = relationship(back_populates="tasks")


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    __table_args__ = (
        Index("ix_executions_research_agent", "research_id", "agent"),
    )

    id: Mapped[uuid.UUID] = _pk()
    research_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_sessions.id", ondelete="CASCADE")
    )
    agent: Mapped[str] = mapped_column(String(32))
    task_key: Mapped[str | None] = mapped_column(String(32))
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[list[str]] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()

    research: Mapped[ResearchSession] = relationship(
        back_populates="executions"
    )


class Source(Base):

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint(
            "research_id", "label", name="uq_sources_research_label"
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    research_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_sessions.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(16))
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("document_chunks.id", ondelete="SET NULL")
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="SET NULL")
    )
    document_name: Mapped[str] = mapped_column(String(255))
    page_number: Mapped[int | None] = mapped_column(Integer)
    snippet: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float, default=0.0)

    research: Mapped[ResearchSession] = relationship(back_populates="sources")


class ResearchFinding(Base):
    __tablename__ = "research_findings"

    id: Mapped[uuid.UUID] = _pk()
    research_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_sessions.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    statement: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16))  # fact | interpretation
    aspect: Mapped[str | None] = mapped_column(String(256))
    support_level: Mapped[str] = mapped_column(String(24))
    verification_note: Mapped[str | None] = mapped_column(Text)

    research: Mapped[ResearchSession] = relationship(back_populates="findings")
    sources: Mapped[list[Source]] = relationship(secondary=finding_sources)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = _pk()
    research_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        unique=True,
    )
    title: Mapped[str] = mapped_column(String(512))
    markdown: Mapped[str] = mapped_column(Text)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    quality: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()

    research: Mapped[ResearchSession] = relationship(back_populates="report")


class ResearchEvent(Base):

    __tablename__ = "research_events"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    research_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_sessions.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(48))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class ResearchMessage(Base):

    __tablename__ = "research_messages"

    id: Mapped[uuid.UUID] = _pk()
    research_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


# ----------------------------- Evaluación
class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"
    __table_args__ = (UniqueConstraint("name", name="uq_eval_datasets_name"),)

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = _created()

    experiments: Mapped[list[EvaluationExperiment]] = relationship(
        back_populates="dataset"
    )


class EvaluationExperiment(Base):
    __tablename__ = "evaluation_experiments"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(128))
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("evaluation_datasets.id", ondelete="RESTRICT"),
        index=True,
    )
    mode: Mapped[str] = mapped_column(String(16))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(TS)

    dataset: Mapped[EvaluationDataset] = relationship(
        back_populates="experiments"
    )
    results: Mapped[list[EvaluationResult]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        UniqueConstraint(
            "experiment_id", "item_id", name="uq_eval_results_item"
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("evaluation_experiments.id", ondelete="CASCADE"),
        index=True,
    )
    item_id: Mapped[str] = mapped_column(String(128))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="completed")
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    retrieved: Mapped[list[str]] = mapped_column(JSONB, default=list)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()

    experiment: Mapped[EvaluationExperiment] = relationship(
        back_populates="results"
    )
