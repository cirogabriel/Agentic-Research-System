"""Esquema inicial: documentos, chunks (pgvector), investigaciones, evaluación.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

from ars.config import get_settings

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DIM = get_settings().embedding_dimensions  # la dimensión queda fijada al crear la columna


def _pk():
    return sa.Column("id", sa.Uuid(), primary_key=True, nullable=False)


def _created():
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        _pk(),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(16), nullable=False),
        sa.Column("title", sa.String(512)),
        sa.Column("author", sa.String(256)),
        sa.Column("document_date", sa.DateTime(timezone=True)),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("num_pages", sa.Integer()),
        sa.Column("num_chunks", sa.Integer(), nullable=False),
        sa.Column("index_signature", sa.String(64)),
        sa.Column("extra", pg.JSONB(), nullable=False),
        _created(),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("filename", name="uq_documents_filename"),
        sa.UniqueConstraint("content_hash", name="uq_documents_content_hash"),
    )
    op.create_index("ix_documents_status", "documents", ["status"])

    op.create_table(
        "document_chunks",
        _pk(),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(DIM), nullable=False),
        sa.Column("search_vector", pg.TSVECTOR(), sa.Computed("to_tsvector('simple', content)", persisted=True)),
        sa.Column("extra", pg.JSONB(), nullable=False),
        _created(),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
    )
    op.create_index("ix_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_chunks_search_vector", "document_chunks", ["search_vector"], postgresql_using="gin")
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "embedding_cache",
        sa.Column("content_hash", sa.String(64), primary_key=True),
        sa.Column("model", sa.String(64), primary_key=True),
        sa.Column("dimensions", sa.Integer(), primary_key=True),
        sa.Column("embedding", Vector(DIM), nullable=False),
        _created(),
    )

    op.create_table(
        "research_sessions",
        _pk(),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("research_sessions.id", ondelete="SET NULL")),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("normalized", pg.JSONB()),
        sa.Column("options", pg.JSONB(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("current_stage", sa.String(48)),
        sa.Column("stop_reason", sa.String(32)),
        sa.Column("clarification_questions", pg.JSONB()),
        sa.Column("run_count", sa.Integer(), nullable=False),
        sa.Column("iterations", sa.Integer(), nullable=False),
        sa.Column("tokens_input", sa.Integer(), nullable=False),
        sa.Column("tokens_output", sa.Integer(), nullable=False),
        sa.Column("embedding_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("error", sa.Text()),
        _created(),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_research_status_created", "research_sessions", ["status", "created_at"])

    op.create_table(
        "research_tasks",
        _pk(),
        sa.Column("research_id", sa.Uuid(), sa.ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(32), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("aspect", sa.String(256)),
        sa.Column("strategy_hint", sa.String(16), nullable=False),
        sa.Column("strategy_used", sa.String(16)),
        sa.Column("transform_used", sa.String(16)),
        sa.Column("queries_used", pg.JSONB(), nullable=False),
        sa.Column("num_evidence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.Text()),
        _created(),
        sa.UniqueConstraint("research_id", "key", name="uq_tasks_research_key"),
    )
    op.create_index("ix_research_tasks_research_id", "research_tasks", ["research_id"])

    op.create_table(
        "agent_executions",
        _pk(),
        sa.Column("research_id", sa.Uuid(), sa.ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent", sa.String(32), nullable=False),
        sa.Column("task_key", sa.String(32)),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("llm_calls", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("tool_calls", pg.JSONB(), nullable=False),
        sa.Column("error", sa.Text()),
        _created(),
    )
    op.create_index("ix_executions_research_agent", "agent_executions", ["research_id", "agent"])

    op.create_table(
        "sources",
        _pk(),
        sa.Column("research_id", sa.Uuid(), sa.ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(16), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("document_chunks.id", ondelete="SET NULL")),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("document_name", sa.String(255), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.UniqueConstraint("research_id", "label", name="uq_sources_research_label"),
    )
    op.create_index("ix_sources_research_id", "sources", ["research_id"])

    op.create_table(
        "research_findings",
        _pk(),
        sa.Column("research_id", sa.Uuid(), sa.ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("aspect", sa.String(256)),
        sa.Column("support_level", sa.String(24), nullable=False),
        sa.Column("verification_note", sa.Text()),
    )
    op.create_index("ix_research_findings_research_id", "research_findings", ["research_id"])

    op.create_table(
        "finding_sources",
        sa.Column("finding_id", sa.Uuid(), sa.ForeignKey("research_findings.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "reports",
        _pk(),
        sa.Column("research_id", sa.Uuid(), sa.ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("content", pg.JSONB(), nullable=False),
        sa.Column("quality", pg.JSONB(), nullable=False),
        _created(),
    )

    op.create_table(
        "research_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("research_id", sa.Uuid(), sa.ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
        _created(),
    )
    op.create_index("ix_research_events_research_id", "research_events", ["research_id"])

    op.create_table(
        "research_messages",
        _pk(),
        sa.Column("research_id", sa.Uuid(), sa.ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        _created(),
    )
    op.create_index("ix_research_messages_research_id", "research_messages", ["research_id"])

    op.create_table(
        "evaluation_datasets",
        _pk(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("items", pg.JSONB(), nullable=False),
        _created(),
        sa.UniqueConstraint("name", name="uq_eval_datasets_name"),
    )

    op.create_table(
        "evaluation_experiments",
        _pk(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("evaluation_datasets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("config", pg.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("summary", pg.JSONB()),
        sa.Column("error", sa.Text()),
        _created(),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_evaluation_experiments_dataset_id", "evaluation_experiments", ["dataset_id"])

    op.create_table(
        "evaluation_results",
        _pk(),
        sa.Column("experiment_id", sa.Uuid(), sa.ForeignKey("evaluation_experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.String(128), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("metrics", pg.JSONB(), nullable=False),
        sa.Column("retrieved", pg.JSONB(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("tokens_input", sa.Integer(), nullable=False),
        sa.Column("tokens_output", sa.Integer(), nullable=False),
        sa.Column("iterations", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text()),
        _created(),
        sa.UniqueConstraint("experiment_id", "item_id", name="uq_eval_results_item"),
    )
    op.create_index("ix_evaluation_results_experiment_id", "evaluation_results", ["experiment_id"])


def downgrade() -> None:
    for table in (
        "evaluation_results", "evaluation_experiments", "evaluation_datasets", "research_messages",
        "research_events", "reports", "finding_sources", "research_findings", "sources", "agent_executions",
        "research_tasks", "research_sessions", "embedding_cache", "document_chunks", "documents",
    ):
        op.drop_table(table)
