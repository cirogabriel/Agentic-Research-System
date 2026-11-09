from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from ars.db.session import session_scope
from ars.llm.budget import ExecutionRecord, UsageTracker
from ars.repositories.research import ResearchRepository

log = logging.getLogger(__name__)


class MemoryReporter:
    """Implementación en memoria (pruebas y evaluación): no toca la base de datos."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.executions: list[dict[str, Any]] = []
        self.current_stage: str | None = None
        self._lock = threading.Lock()

    def event(
        self,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self.events.append(
                {
                    "type": event_type,
                    "message": message,
                    "payload": payload or {},
                }
            )

    def stage(self, name: str) -> None:
        self.current_stage = name

    def sync_usage(
        self, tracker: UsageTracker, iteration: int | None = None
    ) -> None:
        pass

    def _record(self, rec: ExecutionRecord) -> None:
        data = {
            "agent": rec.agent,
            "task_key": rec.task_key,
            "iteration": rec.iteration,
            "status": "failed" if rec.error else "completed",
            "input_tokens": rec.tokens_in,
            "output_tokens": rec.tokens_out,
            "llm_calls": rec.llm_calls,
            "latency_ms": rec.latency_ms,
            "tool_calls": list(rec.tool_calls),
            "error": rec.error,
        }
        with self._lock:
            self.executions.append(data)
        self._persist_execution(data)

    def _persist_execution(self, data: dict[str, Any]) -> None:
        pass

    @contextmanager
    def execution(
        self, agent: str, task_key: str | None = None, iteration: int = 0
    ) -> Iterator[ExecutionRecord]:
        rec = ExecutionRecord(
            agent=agent, task_key=task_key, iteration=iteration
        )
        try:
            yield rec
        except BaseException as exc:
            rec.error = f"{type(exc).__name__}: {exc}"[:500]
            raise
        finally:
            self._record(rec)


class DbReporter(MemoryReporter):

    def __init__(
        self, session_factory: sessionmaker[Session], research_id: uuid.UUID
    ) -> None:
        super().__init__()
        self._sf, self.research_id = session_factory, research_id

    def _safe(self, fn: Any) -> None:
        try:
            with session_scope(self._sf) as s:
                fn(ResearchRepository(s), s)
        except Exception:
            log.exception(
                "No se pudo persistir el progreso de la investigación"
            )

    def event(
        self,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().event(event_type, message, payload)
        self._safe(
            lambda repo, s: repo.add_event(
                self.research_id, event_type, message, payload
            )
        )

    def stage(self, name: str) -> None:
        super().stage(name)

        def upd(repo: ResearchRepository, s: Session) -> None:
            if (r := repo.get(self.research_id)) is not None:
                r.current_stage = name

        self._safe(upd)

    def sync_usage(
        self, tracker: UsageTracker, iteration: int | None = None
    ) -> None:
        snap = tracker.snapshot()

        def upd(repo: ResearchRepository, s: Session) -> None:
            if (r := repo.get(self.research_id)) is not None:
                r.tokens_input, r.tokens_output = (
                    snap["tokens_input"],
                    snap["tokens_output"],
                )
                r.embedding_tokens, r.cost_usd = (
                    snap["embedding_tokens"],
                    snap["cost_usd"],
                )
                if iteration is not None:
                    r.iterations = iteration

        self._safe(upd)

    def _persist_execution(self, data: dict[str, Any]) -> None:
        self._safe(lambda repo, s: repo.add_execution(self.research_id, **data))
