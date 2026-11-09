from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from ars.db.models import (
    AgentExecution,
    DocumentChunk,
    Report,
    ResearchEvent,
    ResearchFinding,
    ResearchMessage,
    ResearchSession,
    ResearchTask,
    Source,
)
from ars.enums import ResearchStatus


def utcnow() -> datetime:
    return datetime.now(UTC)


class ResearchRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    # ---- sesiones ----
    def create(
        self,
        query: str,
        options: dict[str, Any],
        parent_id: uuid.UUID | None = None,
    ) -> ResearchSession:
        r = ResearchSession(
            query=query,
            options=options,
            parent_id=parent_id,
            status=ResearchStatus.PENDING.value,
        )
        self.s.add(r)
        self.s.flush()  # el id (uuid4) se asigna al hacer flush; el mensaje lo necesita
        self.s.add(
            ResearchMessage(research_id=r.id, role="user", content=query)
        )
        self.s.flush()
        return r

    def get(self, research_id: uuid.UUID) -> ResearchSession | None:
        return self.s.get(ResearchSession, research_id)

    def list(
        self, *, limit: int = 20, offset: int = 0, status: str | None = None
    ) -> tuple[list[ResearchSession], int]:
        stmt = select(ResearchSession)
        if status:
            stmt = stmt.where(ResearchSession.status == status)
        total = (
            self.s.scalar(select(func.count()).select_from(stmt.subquery()))
            or 0
        )
        rows = self.s.scalars(
            stmt.order_by(ResearchSession.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return list(rows), total

    def mark_unfinished_as_interrupted(self) -> int:
     
        res = self.s.execute(
            update(ResearchSession)
            .where(ResearchSession.status.in_(["pending", "running"]))
            .values(
                status=ResearchStatus.INTERRUPTED.value,
                error="Interrumpida por reinicio del servicio",
            )
        )
        return res.rowcount or 0

    # ---- eventos y mensajes ----
    def add_event(
        self,
        research_id: uuid.UUID,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.s.add(
            ResearchEvent(
                research_id=research_id,
                event_type=event_type,
                message=message,
                payload=payload or {},
            )
        )

    def events_after(
        self, research_id: uuid.UUID, after_id: int = 0, limit: int = 200
    ) -> list[ResearchEvent]:
        stmt = (
            select(ResearchEvent)
            .where(
                ResearchEvent.research_id == research_id,
                ResearchEvent.id > after_id,
            )
            .order_by(ResearchEvent.id)
            .limit(limit)
        )
        return list(self.s.scalars(stmt).all())

    def add_message(
        self, research_id: uuid.UUID, role: str, content: str
    ) -> None:
        self.s.add(
            ResearchMessage(research_id=research_id, role=role, content=content)
        )

    def add_execution(self, research_id: uuid.UUID, **fields: Any) -> None:
        self.s.add(AgentExecution(research_id=research_id, **fields))

    # ---- lectura de resultados ----
    def get_report(self, research_id: uuid.UUID) -> Report | None:
        return self.s.scalar(
            select(Report).where(Report.research_id == research_id)
        )

    def sources(self, research_id: uuid.UUID) -> list[Source]:
        return list(
            self.s.scalars(
                select(Source)
                .where(Source.research_id == research_id)
                .order_by(Source.label)
            ).all()
        )

    def findings(self, research_id: uuid.UUID) -> list[ResearchFinding]:
        stmt = (
            select(ResearchFinding)
            .where(ResearchFinding.research_id == research_id)
            .options(selectinload(ResearchFinding.sources))
            .order_by(ResearchFinding.position)
        )
        return list(self.s.scalars(stmt).all())

    def tasks(self, research_id: uuid.UUID) -> list[ResearchTask]:
        return list(
            self.s.scalars(
                select(ResearchTask)
                .where(ResearchTask.research_id == research_id)
                .order_by(ResearchTask.created_at)
            ).all()
        )

    def executions(self, research_id: uuid.UUID) -> list[AgentExecution]:
        return list(
            self.s.scalars(
                select(AgentExecution)
                .where(AgentExecution.research_id == research_id)
                .order_by(AgentExecution.created_at)
            ).all()
        )

    # ---- persistencia del resultado final ----
    def save_outcome(
        self,
        research_id: uuid.UUID,
        state: dict[str, Any],
        usage: dict[str, Any],
    ) -> None:
       
        r = self.s.get(ResearchSession, research_id)
        assert r is not None
        r.normalized = state.get("analysis")
        r.status = state.get("status", ResearchStatus.FAILED.value)
        r.stop_reason = state.get("stop_reason")
        r.iterations = int(state.get("iteration", 0))
        r.clarification_questions = (
            (state.get("analysis") or {}).get("clarification_questions")
            if r.status == "needs_clarification"
            else None
        )
        r.tokens_input, r.tokens_output = (
            usage["tokens_input"],
            usage["tokens_output"],
        )
        r.embedding_tokens, r.cost_usd = (
            usage["embedding_tokens"],
            usage["cost_usd"],
        )
        r.error = "; ".join(state.get("errors", []))[:2000] or None
        r.finished_at = utcnow()

    
        for model in (ResearchTask, ResearchFinding, Source, Report):
            for row in self.s.scalars(
                select(model).where(model.research_id == research_id)
            ).all():
                self.s.delete(row)
        self.s.flush()

        results = {res["task_id"]: res for res in state.get("task_results", [])}
        for t in state.get("tasks", []):
            res = results.get(t["id"], {})
            self.s.add(
                ResearchTask(
                    research_id=research_id,
                    key=t["id"],
                    iteration=t.get("iteration", 1),
                    title=t["title"][:256],
                    question=t["question"],
                    aspect=(t.get("aspect") or None),
                    strategy_hint=t.get("strategy_hint", "auto"),
                    strategy_used=res.get("strategy"),
                    transform_used=res.get("transform"),
                    queries_used=res.get("queries", []),
                    num_evidence=len(res.get("evidence", [])),
                    status="failed"
                    if res.get("error")
                    else ("completed" if res else "pending"),
                    error=res.get("error"),
                )
            )

        sources = state.get("sources", {})
        chunk_ids = [uuid.UUID(s["chunk_id"]) for s in sources.values()]
        alive = (
            set(
                self.s.scalars(
                    select(DocumentChunk.id).where(
                        DocumentChunk.id.in_(chunk_ids)
                    )
                ).all()
            )
            if chunk_ids
            else set()
        )
        doc_alive = (
            {
                d
                for d in self.s.execute(
                    select(DocumentChunk.document_id).where(
                        DocumentChunk.id.in_(alive)
                    )
                ).scalars()
            }
            if alive
            else set()
        )
        by_label: dict[str, Source] = {}
        for label, s in sources.items():
            cid = uuid.UUID(s["chunk_id"])
            src = Source(
                research_id=research_id,
                label=label,
                chunk_id=cid if cid in alive else None,
                document_id=uuid.UUID(s["document_id"])
                if uuid.UUID(s["document_id"]) in doc_alive
                else None,
                document_name=s["document_name"][:255],
                page_number=s.get("page_number"),
                snippet=s["text"][:1500],
                score=float(s.get("score", 0.0)),
            )
            self.s.add(src)
            by_label[label] = src

        for i, f in enumerate(state.get("findings", [])):
            self.s.add(
                ResearchFinding(
                    research_id=research_id,
                    position=i,
                    statement=f["statement"],
                    kind=f.get("kind", "fact"),
                    aspect=(f.get("aspect") or None),
                    support_level=f.get("support", "unverified"),
                    verification_note=f.get("note") or None,
                    sources=[
                        by_label[lb]
                        for lb in f.get("labels", [])
                        if lb in by_label
                    ],
                )
            )

        report = state.get("report")
        if report:
            self.s.add(
                Report(
                    research_id=research_id,
                    title=report["title"][:512],
                    markdown=report["markdown"],
                    content=report.get("content", {}),
                    quality=state.get("quality", {}),
                )
            )
            self.add_message(
                research_id,
                "assistant",
                report.get("summary", report["title"])[:4000],
            )
        self.s.flush()
