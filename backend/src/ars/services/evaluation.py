"""Casos de uso de evaluación: datasets, experimentos (A/B/C/recuperación) y comparación."""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from ars.db.models import EvaluationDataset, EvaluationExperiment
from ars.db.session import session_scope
from ars.evaluation.experiments import ExperimentRunner, flatten
from ars.evaluation.generation_metrics import evaluate_generation
from ars.exceptions import ConflictError, NotFoundError
from ars.repositories.evaluation import EvaluationRepository
from ars.schemas.api import DatasetCreate, EvaluationCreate

if TYPE_CHECKING:
    from ars.runtime import AppContainer

log = logging.getLogger(__name__)


class EvaluationService:
    def __init__(self, container: AppContainer) -> None:
        self.c = container

    # ---- datasets ----
    def create_dataset(self, data: DatasetCreate) -> EvaluationDataset:
        with session_scope(self.c.session_factory) as s:
            repo = EvaluationRepository(s)
            if repo.get_dataset_by_name(data.name):
                raise ConflictError(f"Ya existe un dataset llamado '{data.name}'")
            return repo.create_dataset(data.name, data.description, [i.model_dump() for i in data.items])

    def list_datasets(self) -> list[EvaluationDataset]:
        with session_scope(self.c.session_factory) as s:
            return EvaluationRepository(s).list_datasets()

    def get_dataset(self, dataset_id: uuid.UUID) -> EvaluationDataset:
        with session_scope(self.c.session_factory) as s:
            ds = EvaluationRepository(s).get_dataset(dataset_id)
            if ds is None:
                raise NotFoundError(f"Dataset {dataset_id} no encontrado")
            return ds

    # ---- experimentos ----
    def create(self, req: EvaluationCreate) -> EvaluationExperiment:
        self.get_dataset(req.dataset_id)
        cfg = req.model_dump(mode="json", exclude={"name", "dataset_id", "mode"})
        with session_scope(self.c.session_factory) as s:
            return EvaluationRepository(s).create_experiment(req.name, req.dataset_id, req.mode, cfg)

    def enqueue(self, experiment_id: uuid.UUID) -> None:
        self.c.runner.submit(self.run, experiment_id)

    def run(self, experiment_id: uuid.UUID) -> None:
        with session_scope(self.c.session_factory) as s:
            repo = EvaluationRepository(s)
            exp = repo.get_experiment(experiment_id)
            if exp is None:
                return
            exp.status = "running"
            mode, cfg = exp.mode, dict(exp.config)
            items = list(repo.get_dataset(exp.dataset_id).items)  # type: ignore[union-attr]
        runner = ExperimentRunner(self.c)
        collected: list[dict[str, Any]] = []
        try:
            for item in items:
                try:
                    if mode == "retrieval":
                        res = runner.run_retrieval_item(item, cfg)
                    elif mode == "A":
                        res = runner.run_baseline_item(item, cfg)
                    else:
                        res = runner.run_agent_item(item, cfg, mode)
                    res.setdefault("status", "completed")
                    error = None
                except Exception as exc:  # un ítem fallido no invalida el experimento completo
                    log.exception("Ítem de evaluación falló", extra={"item": item["id"]})
                    res = {"metrics": {}, "retrieved": [], "answer": None, "latency_ms": 0, "tokens_in": 0, "tokens_out": 0, "iterations": 0, "outcome": None, "status": "error"}
                    error = f"{type(exc).__name__}: {exc}"[:500]
                collected.append(res)
                with session_scope(self.c.session_factory) as s:
                    EvaluationRepository(s).add_result(
                        experiment_id, item_id=item["id"], question=item["question"], answer=res["answer"], status="failed" if res["status"] in {"error", "failed"} else "completed",
                        metrics=res["metrics"], retrieved=res["retrieved"], latency_ms=res["latency_ms"], tokens_input=res["tokens_in"], tokens_output=res["tokens_out"],
                        iterations=res["iterations"], error=error)
            summary = runner.summarize(mode, collected)
            if cfg.get("use_ragas") and mode != "retrieval":
                summary["ragas"] = self._ragas(items, collected)
            with session_scope(self.c.session_factory) as s:
                EvaluationRepository(s).finish_experiment(experiment_id, "completed", summary)
        except Exception as exc:
            log.exception("Experimento fallido")
            with session_scope(self.c.session_factory) as s:
                EvaluationRepository(s).finish_experiment(experiment_id, "failed", None, f"{type(exc).__name__}: {exc}"[:1000])

    def _ragas(self, items: list[dict[str, Any]], collected: list[dict[str, Any]]) -> dict[str, Any]:
        from ars.evaluation.ragas_runner import run_ragas

        samples = [{"question": it["question"], "answer": r.get("answer") or "", "contexts": r.get("contexts", []), "reference": it.get("reference_answer")}
                   for it, r in zip(items, collected, strict=True) if r.get("answer")]
        try:
            means, _ = run_ragas(samples, self.c.settings)
            return means
        except Exception as exc:  # Ragas es opcional: su fallo no debe invalidar las métricas deterministas
            log.warning("Ragas no pudo ejecutarse: %s", exc)
            return {"error": str(exc)[:300]}

    def evaluate_answer(self, question: str, answer: str, contexts: list[str], reference: str | None) -> dict[str, float]:
        return evaluate_generation(question, answer, contexts, reference)

    def get(self, experiment_id: uuid.UUID, with_results: bool = False) -> EvaluationExperiment:
        with session_scope(self.c.session_factory) as s:
            exp = EvaluationRepository(s).get_experiment(experiment_id, with_results)
            if exp is None:
                raise NotFoundError(f"Evaluación {experiment_id} no encontrada")
            return exp

    def list(self, limit: int, offset: int, dataset_id: uuid.UUID | None) -> tuple[list[EvaluationExperiment], int]:
        with session_scope(self.c.session_factory) as s:
            return EvaluationRepository(s).list_experiments(limit=limit, offset=offset, dataset_id=dataset_id)

    # ---- comparación ----
    def compare(self, experiment_ids: list[uuid.UUID] | None, dataset_id: uuid.UUID | None) -> dict[str, Any]:
        with session_scope(self.c.session_factory) as s:
            repo = EvaluationRepository(s)
            if experiment_ids:
                exps = [e for i in experiment_ids if (e := repo.get_experiment(i)) is not None]
            else:  # último experimento completado de cada modo (A, B, C) para el dataset
                exps, _ = repo.list_experiments(limit=100, dataset_id=dataset_id)
                latest: dict[str, EvaluationExperiment] = {}
                for e in exps:
                    if e.status == "completed" and e.mode in {"A", "B", "C"}:
                        latest.setdefault(e.mode, e)
                exps = [latest[m] for m in ("A", "B", "C") if m in latest]
            exps = [e for e in exps if e.status == "completed" and e.summary]
            if len(exps) < 2:
                raise ConflictError("Se necesitan al menos 2 experimentos completados para comparar")
            baseline = next((e for e in exps if e.mode == "A"), exps[0])
            rows = [{"id": str(e.id), "name": e.name, "mode": e.mode, "dataset_id": str(e.dataset_id), "metrics": flatten(e.summary or {})} for e in exps]
            base_metrics = flatten(baseline.summary or {})
            deltas = {str(e.id): {k: (round(v - base_metrics[k], 4) if k in base_metrics else None) for k, v in flatten(e.summary or {}).items()}
                      for e in exps if e.id != baseline.id}
            return {"baseline_id": baseline.id, "experiments": rows, "deltas": deltas}
