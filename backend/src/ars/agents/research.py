"""Research Agent: ejecuta una subtarea con las herramientas de recuperación. No usa el LLM directamente
(solo indirectamente, si el router decide transformar la consulta), de modo que su coste es bajo."""
from __future__ import annotations

import logging

from ars.agents.toolbox import RetrievalToolbox
from ars.exceptions import BudgetExceededError
from ars.llm.budget import ExecutionRecord
from ars.schemas.agents import EvidenceItem, SubTask, TaskResult
from ars.schemas.rag import RetrievalRequest, RetrievalResult, SearchFilters

log = logging.getLogger(__name__)


class ResearchAgent:
    def __init__(self, toolbox: RetrievalToolbox, top_k: int, filters: SearchFilters | None = None, strategy: str = "auto", transform: str = "auto") -> None:
        self.toolbox, self.top_k, self.filters = toolbox, top_k, filters
        self.default_strategy, self.default_transform = strategy, transform

    def _request(self, task: SubTask, strategy: str | None = None, transform: str | None = None) -> RetrievalRequest:
        s = strategy or (task.strategy_hint if task.strategy_hint != "auto" else self.default_strategy)
        t = transform or (task.transform_hint if task.transform_hint != "auto" else self.default_transform)
        return RetrievalRequest(query=task.question, strategy=s, transform=t, top_k=self.top_k, filters=self.filters)  # type: ignore[arg-type]

    def run(self, task: SubTask, rec: ExecutionRecord | None = None) -> TaskResult:
        try:
            result = self._retrieve(self._request(task), rec)
            if not result.chunks and result.decision.strategy != "hybrid":
                # Fallback de código (sin LLM): si no hubo resultados, se reintenta híbrido.
                result = self._retrieve(self._request(task, strategy="hybrid", transform="none"), rec)
        except Exception as exc:
            log.warning("Subtarea %s falló: %s", task.id, exc)
            return TaskResult(task_id=task.id, iteration=task.iteration, error=f"{type(exc).__name__}: {exc}"[:500])
        evidence = [
            EvidenceItem(chunk_id=str(c.chunk_id), document_id=str(c.document_id), document_name=c.document_name, page_number=c.page_number,
                         chunk_index=c.chunk_index, text=c.content, score=c.score)
            for c in result.chunks
        ]
        return TaskResult(task_id=task.id, iteration=task.iteration, strategy=result.decision.strategy, transform=result.decision.transform,
                          queries=result.queries, evidence=evidence)

    def _retrieve(self, req: RetrievalRequest, rec: ExecutionRecord | None) -> RetrievalResult:
        try:
            return self.toolbox.retrieve(req, rec)
        except BudgetExceededError:
            # Sin presupuesto no se puede transformar la consulta con el LLM, pero sí buscar con la consulta original.
            return self.toolbox.retrieve(req.model_copy(update={"transform": "none"}), rec)
