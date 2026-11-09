from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from starlette.concurrency import run_in_threadpool

from ars.api.deps import get_evaluation_service, require_api_key
from ars.schemas.api import (
    ComparisonOut,
    DatasetCreate,
    DatasetOut,
    EvaluationCreate,
    EvaluationDetailOut,
    EvaluationListOut,
    EvaluationOut,
)
from ars.services.evaluation import EvaluationService

router = APIRouter(
    prefix="/evaluations",
    tags=["evaluations"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "/datasets",
    response_model=DatasetOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un dataset de evaluación",
)
async def create_dataset(
    body: DatasetCreate,
    svc: EvaluationService = Depends(get_evaluation_service),
) -> DatasetOut:
    return DatasetOut.model_validate(
        await run_in_threadpool(svc.create_dataset, body)
    )


@router.get("/datasets", response_model=list[DatasetOut])
async def list_datasets(
    svc: EvaluationService = Depends(get_evaluation_service),
) -> list[DatasetOut]:
    return [
        DatasetOut.model_validate(d)
        for d in await run_in_threadpool(svc.list_datasets)
    ]


@router.post(
    "",
    response_model=EvaluationOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Lanzar un experimento (retrieval, A, B o C)",
)
async def create_evaluation(
    body: EvaluationCreate,
    svc: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationOut:
    exp = await run_in_threadpool(svc.create, body)
    svc.enqueue(exp.id)
    return EvaluationOut.model_validate(exp)


@router.get("", response_model=EvaluationListOut)
async def list_evaluations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    dataset_id: uuid.UUID | None = None,
    svc: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationListOut:
    rows, total = await run_in_threadpool(svc.list, limit, offset, dataset_id)
    return EvaluationListOut(
        items=[EvaluationOut.model_validate(e) for e in rows], total=total
    )



@router.get(
    "/experiments/compare",
    response_model=ComparisonOut,
    summary="Comparar experimentos A/B/C",
)
async def compare(
    experiment_ids: list[uuid.UUID] | None = Query(None),
    dataset_id: uuid.UUID | None = None,
    svc: EvaluationService = Depends(get_evaluation_service),
) -> ComparisonOut:
    return ComparisonOut(
        **await run_in_threadpool(svc.compare, experiment_ids, dataset_id)
    )


@router.get("/{evaluation_id}", response_model=EvaluationDetailOut)
async def get_evaluation(
    evaluation_id: uuid.UUID,
    svc: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationDetailOut:
    exp = await run_in_threadpool(svc.get, evaluation_id, True)
    return EvaluationDetailOut.model_validate(exp)
