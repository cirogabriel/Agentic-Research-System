from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ars.db.models import (
    EvaluationDataset,
    EvaluationExperiment,
    EvaluationResult,
)
from ars.repositories.research import utcnow


class EvaluationRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    # ---- datasets ----
    def create_dataset(
        self, name: str, description: str | None, items: list[dict[str, Any]]
    ) -> EvaluationDataset:
        ds = EvaluationDataset(name=name, description=description, items=items)
        self.s.add(ds)
        self.s.flush()
        return ds

    def get_dataset(self, dataset_id: uuid.UUID) -> EvaluationDataset | None:
        return self.s.get(EvaluationDataset, dataset_id)

    def get_dataset_by_name(self, name: str) -> EvaluationDataset | None:
        return self.s.scalar(
            select(EvaluationDataset).where(EvaluationDataset.name == name)
        )

    def list_datasets(self) -> list[EvaluationDataset]:
        return list(
            self.s.scalars(
                select(EvaluationDataset).order_by(
                    EvaluationDataset.created_at.desc()
                )
            ).all()
        )

    # ---- experimentos ----
    def create_experiment(
        self,
        name: str,
        dataset_id: uuid.UUID,
        mode: str,
        config: dict[str, Any],
    ) -> EvaluationExperiment:
        exp = EvaluationExperiment(
            name=name,
            dataset_id=dataset_id,
            mode=mode,
            config=config,
            status="pending",
        )
        self.s.add(exp)
        self.s.flush()
        return exp

    def get_experiment(
        self, experiment_id: uuid.UUID, with_results: bool = False
    ) -> EvaluationExperiment | None:
        stmt = select(EvaluationExperiment).where(
            EvaluationExperiment.id == experiment_id
        )
        if with_results:
            stmt = stmt.options(selectinload(EvaluationExperiment.results))
        return self.s.scalar(stmt)

    def list_experiments(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        dataset_id: uuid.UUID | None = None,
    ) -> tuple[list[EvaluationExperiment], int]:
        stmt = select(EvaluationExperiment)
        if dataset_id:
            stmt = stmt.where(EvaluationExperiment.dataset_id == dataset_id)
        total = (
            self.s.scalar(select(func.count()).select_from(stmt.subquery()))
            or 0
        )
        rows = self.s.scalars(
            stmt.order_by(EvaluationExperiment.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return list(rows), total

    def add_result(self, experiment_id: uuid.UUID, **fields: Any) -> None:
        self.s.add(EvaluationResult(experiment_id=experiment_id, **fields))

    def finish_experiment(
        self,
        experiment_id: uuid.UUID,
        status: str,
        summary: dict[str, Any] | None,
        error: str | None = None,
    ) -> None:
        exp = self.s.get(EvaluationExperiment, experiment_id)
        assert exp is not None
        exp.status, exp.summary, exp.error, exp.finished_at = (
            status,
            summary,
            error,
            utcnow(),
        )
