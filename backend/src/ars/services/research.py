
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from ars.db.models import ResearchSession
from ars.db.session import session_scope
from ars.enums import ResearchStatus
from ars.exceptions import ConflictError, NotFoundError
from ars.graph.nodes import GraphOptions
from ars.graph.reporter import DbReporter
from ars.graph.runner import run_research
from ars.repositories.research import ResearchRepository, utcnow
from ars.schemas.api import ResearchOptions
from ars.schemas.rag import SearchFilters
from ars.utils.text import truncate_chars

if TYPE_CHECKING:
    from ars.runtime import AppContainer

log = logging.getLogger(__name__)


class ResearchService:
    def __init__(self, container: AppContainer) -> None:
        self.c = container

    # ---- creación ----
    def create(
        self,
        query: str,
        options: ResearchOptions,
        parent_id: uuid.UUID | None = None,
    ) -> ResearchSession:
        with session_scope(self.c.session_factory) as s:
            repo = ResearchRepository(s)
            if parent_id is not None and repo.get(parent_id) is None:
                raise NotFoundError(
                    f"Investigación previa {parent_id} no encontrada"
                )
            return repo.create(
                query.strip(), options.model_dump(mode="json"), parent_id
            )

    def enqueue(
        self,
        research_id: uuid.UUID,
        *,
        resume: bool = False,
        skip_clarification: bool = False,
    ) -> None:
        self.c.runner.submit(
            self.execute,
            research_id,
            resume=resume,
            skip_clarification=skip_clarification,
        )

    def _graph_options(self, raw: dict[str, Any]) -> GraphOptions:
        st = self.c.settings
        filters = (
            SearchFilters(document_ids=raw["document_ids"])
            if raw.get("document_ids")
            else None
        )
        return GraphOptions(
            parallel=raw.get("parallel", True),
            allow_reinvestigation=raw.get("reinvestigate", True),
            max_iterations=raw.get("max_iterations"),
            top_k=raw.get("top_k") or st.retrieval_top_k,
            strategy=raw.get("retrieval_strategy") or "auto",
            transform=raw.get("query_transform") or "auto",
            filters=filters,
        )

    # ---- ejecución ----
    def execute(
        self,
        research_id: uuid.UUID,
        *,
        resume: bool = False,
        skip_clarification: bool = False,
    ) -> None:
        with session_scope(self.c.session_factory) as s:
            repo = ResearchRepository(s)
            r = repo.get(research_id)
            if r is None:
                return
            query, raw = r.query, dict(r.options or {})
            parent_context = self._parent_context(repo, r.parent_id)
            prior = (r.tokens_input, r.tokens_output, r.embedding_tokens)
            r.status, r.error, r.started_at, r.finished_at = (
                ResearchStatus.RUNNING.value,
                None,
                r.started_at or utcnow(),
                None,
            )
            if not resume:
                r.run_count += 1
            thread_id = f"{research_id}-{r.run_count}"
        tracker = self.c.new_tracker(raw.get("token_budget"))
        if resume:
            tracker.restore(*prior)
        reporter = DbReporter(self.c.session_factory, research_id)
        try:
            final = run_research(
                settings=self.c.settings,
                query=query,
                options=self._graph_options(raw),
                reporter=reporter,
                tracker=tracker,
                thread_id=thread_id,
                retrieval=self.c.retrieval,
                llm=self.c.new_llm(tracker),
                checkpointer=self.c.checkpointer,
                parent_context=parent_context,
                skip_clarification=skip_clarification,
                resume=resume,
                research_id=str(research_id),
            )
            if "status" not in final:
                final["status"] = ResearchStatus.FAILED.value
            with session_scope(self.c.session_factory) as s:
                ResearchRepository(s).save_outcome(
                    research_id, final, tracker.snapshot()
                )
        except Exception as exc:
            log.exception(
                "Investigación fallida", extra={"research_id": str(research_id)}
            )
            reporter.event("research.failed", f"Error: {exc}")
            with session_scope(self.c.session_factory) as s:
                if (r := ResearchRepository(s).get(research_id)) is not None:
                    r.status, r.error, r.stop_reason, r.finished_at = (
                        ResearchStatus.FAILED.value,
                        f"{type(exc).__name__}: {exc}"[:1500],
                        "error",
                        utcnow(),
                    )
                    snap = tracker.snapshot()
                    r.tokens_input, r.tokens_output, r.cost_usd = (
                        snap["tokens_input"],
                        snap["tokens_output"],
                        snap["cost_usd"],
                    )

    @staticmethod
    def _parent_context(
        repo: ResearchRepository, parent_id: uuid.UUID | None
    ) -> str:
      
        if parent_id is None:
            return ""
        report = repo.get_report(parent_id)
        parent = repo.get(parent_id)
        if report is None or parent is None:
            return ""
        return truncate_chars(
            f"Previous question: {parent.query}\nPrevious report: {report.title}. {report.content.get('executive_summary', '')}",
            1200,
        )

    # ---- aclaraciones y reanudación ----
    def clarify(self, research_id: uuid.UUID, answer: str) -> ResearchSession:
        with session_scope(self.c.session_factory) as s:
            repo = ResearchRepository(s)
            r = repo.get(research_id)
            if r is None:
                raise NotFoundError(
                    f"Investigación {research_id} no encontrada"
                )
            if r.status != ResearchStatus.NEEDS_CLARIFICATION.value:
                raise ConflictError(
                    "La investigación no está esperando aclaraciones"
                )
            r.query = f"{r.query}\nAclaración del usuario: {answer.strip()}"
            r.status = ResearchStatus.PENDING.value
            repo.add_message(research_id, "user", answer)
        self.enqueue(research_id, skip_clarification=True)
        return self.get(research_id)

    def resume(self, research_id: uuid.UUID) -> ResearchSession:
        r = self.get(research_id)
        if r.status not in {
            ResearchStatus.INTERRUPTED.value,
            ResearchStatus.FAILED.value,
        }:
            raise ConflictError(
                "Solo se pueden reanudar investigaciones interrumpidas o fallidas"
            )
        if self.c.checkpointer is None:
            raise ConflictError(
                "El checkpointing está desactivado: no hay estado que reanudar"
            )
        self.enqueue(research_id, resume=True)
        return r

    def mark_interrupted_on_startup(self) -> int:
        with session_scope(self.c.session_factory) as s:
            return ResearchRepository(s).mark_unfinished_as_interrupted()

    # ---- consultas ----
    def get(self, research_id: uuid.UUID) -> ResearchSession:
        with session_scope(self.c.session_factory) as s:
            r = ResearchRepository(s).get(research_id)
            if r is None:
                raise NotFoundError(
                    f"Investigación {research_id} no encontrada"
                )
            return r

    def list(
        self, limit: int, offset: int, status: str | None
    ) -> tuple[list[ResearchSession], int]:
        with session_scope(self.c.session_factory) as s:
            return ResearchRepository(s).list(
                limit=limit, offset=offset, status=status
            )

    def report_bundle(self, research_id: uuid.UUID) -> dict[str, Any]:
        with session_scope(self.c.session_factory) as s:
            repo = ResearchRepository(s)
            r = repo.get(research_id)
            if r is None:
                raise NotFoundError(
                    f"Investigación {research_id} no encontrada"
                )
            report = repo.get_report(research_id)
            if report is None:
                raise ConflictError(
                    f"El informe aún no está disponible (estado: {r.status})"
                )
            findings = [
                {
                    "statement": f.statement,
                    "kind": f.kind,
                    "aspect": f.aspect,
                    "support_level": f.support_level,
                    "verification_note": f.verification_note,
                    "sources": sorted(x.label for x in f.sources),
                }
                for f in repo.findings(research_id)
            ]
            return {
                "research_id": research_id,
                "title": report.title,
                "markdown": report.markdown,
                "content": report.content,
                "quality": report.quality,
                "sources": repo.sources(research_id),
                "findings": findings,
                "created_at": report.created_at,
            }

    def events_after(
        self, research_id: uuid.UUID, after_id: int
    ) -> tuple[list[Any], str]:
        with session_scope(self.c.session_factory) as s:
            repo = ResearchRepository(s)
            r = repo.get(research_id)
            if r is None:
                raise NotFoundError(
                    f"Investigación {research_id} no encontrada"
                )
            return repo.events_after(research_id, after_id), r.status
