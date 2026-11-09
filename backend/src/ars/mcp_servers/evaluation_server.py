
from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import Field

from ars.evaluation.experiments import ExperimentRunner, flatten
from ars.mcp_servers.common import bootstrap, make_server, run
from ars.mcp_servers.schemas import (
    AnswerEvaluation,
    ExperimentComparison,
    ExperimentMetrics,
    RetrievalEvaluation,
)
from ars.runtime import AppContainer
from ars.schemas.api import EvaluationCreate


def create_server(container: AppContainer): 
    mcp = make_server(
        "ars-evaluation",
        "Evaluación objetiva de la recuperación y de las respuestas.",
    )
    svc = container.evaluation

    @mcp.tool()
    def evaluate_retrieval(
        dataset_id: str,
        strategy: Literal["vector", "keyword", "hybrid"] = "hybrid",
        top_k: Annotated[int, Field(ge=1, le=20)] = 5,
        rerank: bool = True,
    ) -> RetrievalEvaluation:

        exp = svc.create(
            EvaluationCreate(
                name=f"mcp-retrieval-{strategy}",
                dataset_id=uuid.UUID(dataset_id),
                mode="retrieval",
                top_k=top_k,
                retrieval_strategy=strategy,
                rerank=rerank,
            )
        )
        svc.run(exp.id)
        done = svc.get(exp.id)
        return RetrievalEvaluation(
            experiment_id=str(done.id),
            status=done.status,
            summary=flatten(done.summary or {}),
        )

    @mcp.tool()
    def evaluate_answer(
        question: str,
        answer: str,
        contexts: list[str],
        reference: str | None = None,
    ) -> AnswerEvaluation:

        return AnswerEvaluation(
            metrics=svc.evaluate_answer(question, answer, contexts, reference)
        )

    @mcp.tool()
    def compare_experiments(
        experiment_ids: Annotated[list[str], Field(min_length=2, max_length=6)],
    ) -> ExperimentComparison:
      
        data = svc.compare([uuid.UUID(i) for i in experiment_ids], None)
        return ExperimentComparison(
            baseline_id=str(data["baseline_id"]),
            experiments=data["experiments"],
            deltas=data["deltas"],
        )

    @mcp.tool()
    def get_evaluation_metrics(experiment_id: str) -> ExperimentMetrics:
        """Resumen de métricas de un experimento."""
        e = svc.get(uuid.UUID(experiment_id))
        return ExperimentMetrics(
            experiment_id=str(e.id),
            mode=e.mode,
            status=e.status,
            summary=e.summary,
        )

    _ = ExperimentRunner  
    return mcp


def main() -> None:
    container, transport = bootstrap()
    run(create_server(container), transport)


if __name__ == "__main__":
    main()
# (referencia explícita: el runner es el que calcula las métricas)