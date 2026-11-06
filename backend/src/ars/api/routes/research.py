from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from ars.api.deps import get_research_service, require_api_key
from ars.enums import ResearchStatus
from ars.schemas.api import (
    ClarificationIn,
    EventOut,
    ReportOut,
    ResearchCreate,
    ResearchListOut,
    ResearchOut,
    ResearchStatusOut,
)
from ars.services.research import ResearchService

router = APIRouter(prefix="/research", tags=["research"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=ResearchOut, status_code=status.HTTP_202_ACCEPTED, summary="Crear y lanzar una investigación (asíncrona)")
async def create_research(body: ResearchCreate, svc: ResearchService = Depends(get_research_service)) -> ResearchOut:
    r = await run_in_threadpool(svc.create, body.query, body.options, body.parent_research_id)
    svc.enqueue(r.id)  # la petición vuelve de inmediato; el progreso se consulta por /status o /events
    return ResearchOut.model_validate(r)


@router.get("", response_model=ResearchListOut)
async def list_research(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), status_: str | None = Query(None, alias="status"),
                        svc: ResearchService = Depends(get_research_service)) -> ResearchListOut:
    rows, total = await run_in_threadpool(svc.list, limit, offset, status_)
    return ResearchListOut(items=[ResearchOut.model_validate(r) for r in rows], total=total)


@router.get("/{research_id}", response_model=ResearchOut)
async def get_research(research_id: uuid.UUID, svc: ResearchService = Depends(get_research_service)) -> ResearchOut:
    return ResearchOut.model_validate(await run_in_threadpool(svc.get, research_id))


@router.get("/{research_id}/status", response_model=ResearchStatusOut)
async def get_status(research_id: uuid.UUID, svc: ResearchService = Depends(get_research_service)) -> ResearchStatusOut:
    r = await run_in_threadpool(svc.get, research_id)
    return ResearchStatusOut(id=r.id, status=r.status, current_stage=r.current_stage, iteration=r.iterations, tokens_input=r.tokens_input,
                             tokens_output=r.tokens_output, embedding_tokens=r.embedding_tokens, cost_usd=float(r.cost_usd),
                             clarification_questions=r.clarification_questions, error=r.error, started_at=r.started_at, finished_at=r.finished_at)


@router.get("/{research_id}/report", response_model=ReportOut, responses={200: {"content": {"text/markdown": {}}}})
async def get_report(research_id: uuid.UUID, format: str = Query("json", pattern="^(json|markdown)$"), svc: ResearchService = Depends(get_research_service)) -> Response | ReportOut:
    bundle = await run_in_threadpool(svc.report_bundle, research_id)
    if format == "markdown":
        return PlainTextResponse(bundle["markdown"], media_type="text/markdown")
    return ReportOut(**bundle)


@router.post("/{research_id}/clarifications", response_model=ResearchOut, status_code=status.HTTP_202_ACCEPTED, summary="Responder a las aclaraciones solicitadas")
async def clarify(research_id: uuid.UUID, body: ClarificationIn, svc: ResearchService = Depends(get_research_service)) -> ResearchOut:
    return ResearchOut.model_validate(await run_in_threadpool(svc.clarify, research_id, body.answer))


@router.post("/{research_id}/resume", response_model=ResearchOut, status_code=status.HTTP_202_ACCEPTED, summary="Reanudar desde el último checkpoint")
async def resume(research_id: uuid.UUID, svc: ResearchService = Depends(get_research_service)) -> ResearchOut:
    return ResearchOut.model_validate(await run_in_threadpool(svc.resume, research_id))


@router.get("/{research_id}/events", summary="Eventos de progreso (SSE; ?stream=false devuelve JSON)", response_model=None)
async def events(research_id: uuid.UUID, stream: bool = Query(True), last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
                 svc: ResearchService = Depends(get_research_service)) -> StreamingResponse | list[EventOut]:
    after = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
    rows, _ = await run_in_threadpool(svc.events_after, research_id, after)  # 404 si no existe
    if not stream:
        return [EventOut.model_validate(e) for e in rows]

    async def generator() -> AsyncIterator[str]:
        cursor = after
        idle = 0
        while True:
            batch, st = await run_in_threadpool(svc.events_after, research_id, cursor)
            for e in batch:
                cursor = e.id
                data = json.dumps({"type": e.event_type, "message": e.message, "payload": e.payload, "at": e.created_at.isoformat()}, default=str)
                yield f"id: {e.id}\nevent: {e.event_type}\ndata: {data}\n\n"
            if st in ResearchStatus.terminal() and not batch:
                yield "event: end\ndata: {}\n\n"
                return
            idle = 0 if batch else idle + 1
            if idle and idle % 20 == 0:
                yield ": keep-alive\n\n"  # comentario SSE para mantener viva la conexión
            await asyncio.sleep(0.75)

    return StreamingResponse(generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
