
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from ars.config import Settings, get_settings
from ars.db.session import (
    check_vector_dimension,
    make_engine,
    make_session_factory,
)
from ars.llm.budget import UsageTracker
from ars.llm.gateway import LLMGateway
from ars.rag.embeddings import EmbeddingService
from ars.rag.ingestion import IndexingPipeline
from ars.rag.reranker import Reranker, build_reranker
from ars.rag.retrieval import RetrievalService
from ars.storage import FileStorage
from ars.tasks.runner import BackgroundRunner

log = logging.getLogger(__name__)


class AppContainer:
    def __init__(
        self,
        settings: Settings,
        engine: Engine,
        session_factory: sessionmaker[Session],
        embeddings: EmbeddingService,
        reranker: Reranker,
        runner: Any,
        checkpointer: Any | None = None,
        pool: Any | None = None,
    ) -> None:
        from ars.services.documents import DocumentService
        from ars.services.evaluation import EvaluationService
        from ars.services.research import ResearchService

        self.settings, self.engine, self.session_factory = (
            settings,
            engine,
            session_factory,
        )
        self.embeddings, self.reranker, self.runner = (
            embeddings,
            reranker,
            runner,
        )
        self.checkpointer, self._pool = checkpointer, pool
        self.storage = FileStorage(settings.storage_dir)
        self.retrieval = RetrievalService(
            settings, session_factory, embeddings, reranker
        )
        self.pipeline = IndexingPipeline(settings, embeddings)
        self.documents = DocumentService(
            settings,
            session_factory,
            self.storage,
            self.pipeline,
            self.retrieval.cache,
        )
        self.research = ResearchService(self)
        self.evaluation = EvaluationService(self)

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        *,
        with_checkpointer: bool = True,
        with_runner: bool = True,
    ) -> AppContainer:
        settings = settings or get_settings()
        engine = make_engine(settings)
        sf = make_session_factory(engine)
        checkpointer, pool = None, None
        if with_checkpointer and settings.checkpointing_enabled:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            # Requisitos de PostgresSaver: autocommit, row_factory=dict_row y sin prepared statements.
            pool = ConnectionPool(
                settings.checkpoint_conninfo,
                max_size=10,
                open=True,
                kwargs={
                    "autocommit": True,
                    "prepare_threshold": 0,
                    "row_factory": dict_row,
                },
            )
            checkpointer = PostgresSaver(pool)
            checkpointer.setup()  
        runner = (
            BackgroundRunner(settings.background_workers)
            if with_runner
            else None
        )
        return cls(
            settings,
            engine,
            sf,
            EmbeddingService(settings, sf),
            build_reranker(settings),
            runner,
            checkpointer,
            pool,
        )

    def verify_schema(self) -> None:
        check_vector_dimension(
            self.session_factory, self.settings.embedding_dimensions
        )

    def new_tracker(self, token_budget: int | None = None) -> UsageTracker:
        return UsageTracker.from_settings(self.settings, token_budget)

    def new_llm(self, tracker: UsageTracker) -> LLMGateway:
        return LLMGateway(self.settings, tracker)

    def close(self) -> None:
        if self.runner is not None:
            self.runner.shutdown()
        if self._pool is not None:
            self._pool.close()
        self.engine.dispose()
