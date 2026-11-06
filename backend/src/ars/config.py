"""Configuración centralizada. Todo se controla por variables de entorno (ver .env.example)."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Aplicación ---
    app_env: str = "development"
    log_level: str = "INFO"
    log_json: bool = True
    api_key: SecretStr | None = None
    cors_origins: list[str] = []
    background_workers: int = 4

    # --- Persistencia / archivos ---
    database_url: str = "postgresql+psycopg://ars:ars@localhost:5432/ars"
    db_pool_size: int = 10
    storage_dir: str = "./storage"
    max_upload_mb: int = 25
    max_pdf_pages: int = 500
    max_uncompressed_mb: int = 200
    checkpointing_enabled: bool = True

    # --- OpenAI (un único modelo generativo para todos los agentes) ---
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    llm_max_output_tokens: int = 1200
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    llm_price_input_per_mtok: float = 0.15
    llm_price_output_per_mtok: float = 0.60

    # --- Embeddings (modelo distinto del generativo) ---
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 64
    embedding_price_per_mtok: float = 0.02

    # --- Chunking ---
    chunk_strategy: Literal["recursive", "fixed", "sentence"] = "recursive"
    chunk_size: int = 1000
    chunk_overlap: int = 150
    chunk_separators: list[str] = ["\n\n", "\n", ". ", " ", ""]

    # --- Recuperación ---
    retrieval_strategy: Literal["auto", "vector", "keyword", "hybrid"] = "auto"
    query_transform: Literal["auto", "none", "rewrite", "multi_query", "rag_fusion", "hyde"] = "auto"
    retrieval_top_k: int = 5
    rrf_k: int = 60
    multi_query_count: int = 3
    hyde_enabled: bool = False
    router_llm_fallback: bool = False
    rerank_enabled: bool = True
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidate_multiplier: int = 4
    rerank_batch_size: int = 16
    rerank_device: str = "cpu"
    retrieval_cache_ttl_seconds: int = 300
    retrieval_cache_size: int = 256

    # --- Agentes ---
    max_iterations: int = 3
    max_subtasks: int = 4
    max_followup_tasks: int = 2
    token_budget: int = 60000
    report_reserve_ratio: float = 0.2
    evidence_per_task: int = 5
    analysis_max_evidence_chars: int = 12000
    max_findings: int = 12
    min_evidence_coverage: float = 0.7
    max_unsupported_ratio: float = 0.25
    verification_mode: Literal["hybrid", "llm", "lexical"] = "hybrid"
    verification_support_threshold: float = 0.6
    verification_max_llm_findings: int = 8
    query_processor_mode: Literal["auto", "always", "never"] = "auto"
    agent_tool_transport: Literal["direct", "mcp"] = "direct"
    message_context_tokens: int = 1500
    message_keep_last: int = 6
    max_parallel_workers: int = 4
    graph_recursion_limit: int = 60

    # --- MCP (cuando se ejecutan como servicios HTTP) ---
    mcp_transport: Literal["stdio", "streamable-http"] = "stdio"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def checkpoint_conninfo(self) -> str:
        """psycopg no entiende el sufijo '+psycopg' del URL de SQLAlchemy."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    def public_dict(self) -> dict[str, Any]:
        """Configuración segura para exponer en la API (sin secretos)."""
        data = self.model_dump()
        data["openai_api_key"] = "configured" if self.openai_api_key.get_secret_value() else "missing"
        data["api_key"] = "configured" if self.api_key and self.api_key.get_secret_value() else "disabled"
        data["database_url"] = re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", self.database_url)
        return data


@lru_cache
def get_settings() -> Settings:
    return Settings()
