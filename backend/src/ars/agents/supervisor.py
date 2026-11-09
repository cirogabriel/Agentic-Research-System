from __future__ import annotations

import re
from typing import Any

from ars.agents import prompts
from ars.config import Settings
from ars.llm.base import StructuredLLM
from ars.llm.budget import ExecutionRecord, UsageTracker
from ars.schemas.agents import ResearchPlan, SubTask, SupervisorDecision
from ars.schemas.query import QueryAnalysis
from ars.utils.text import fold

MIN_TOKENS_FOR_ITERATION = 3000


def _norm(q: str) -> str:
    return re.sub(r"\W+", " ", fold(q)).strip()


class SupervisorAgent:
    def __init__(
        self,
        llm: StructuredLLM,
        settings: Settings,
        max_subtasks: int | None = None,
        max_iterations: int | None = None,
    ) -> None:
        self.llm, self.settings = llm, settings
        self.max_subtasks = max_subtasks or settings.max_subtasks
        self.max_iterations = max_iterations or settings.max_iterations

    # ---- planificación ----
    def plan(
        self,
        analysis: QueryAnalysis,
        parent_context: str = "",
        rec: ExecutionRecord | None = None,
    ) -> tuple[list[SubTask], str]:
        simple = (
            analysis.research_type in {"fact_finding", "descriptive"}
            and len(analysis.key_aspects) <= 2
            and not parent_context
        )
        if simple or self.max_subtasks == 1:
            return [
                SubTask(
                    id="t1",
                    title=analysis.topic[:80] or "Consulta",
                    question=analysis.normalized_query,
                    iteration=1,
                )
            ], "Consulta simple: una única subtarea (sin llamada al LLM)."
        user = (
            f"Research question: {analysis.normalized_query}\nObjective: {analysis.objective}\nType: {analysis.research_type}\n"
            f"Key aspects: {', '.join(analysis.key_aspects)}\nConstraints: {', '.join(analysis.constraints) or 'none'}"
        )
        if parent_context:
            user += f"\nPrevious research context (for resolving references only):\n{parent_context[:1000]}"
        plan = self.llm.structured(
            ResearchPlan,
            system=prompts.PLANNER.format(max_subtasks=self.max_subtasks),
            user=user,
            rec=rec,
            max_tokens=600,
        )
        tasks: list[SubTask] = []
        seen: set[str] = set()
        for p in plan.subtasks:
            key = _norm(p.question)
            if not key or key in seen:
                continue
            seen.add(key)
            tasks.append(
                SubTask(id=f"t{len(tasks) + 1}", iteration=1, **p.model_dump())
            )
            if len(tasks) >= self.max_subtasks:
                break
        if (
            not tasks
        ):  
            tasks = [
                SubTask(
                    id="t1",
                    title=analysis.topic[:80] or "Consulta",
                    question=analysis.normalized_query,
                    iteration=1,
                )
            ]
        return tasks, plan.rationale

    # ---- decisión tras la verificación ----
    def decide(
        self,
        *,
        iteration: int,
        verification: dict[str, Any],
        analysis_notes: dict[str, Any],
        tasks: list[dict[str, Any]],
        tracker: UsageTracker,
        allow_reinvestigation: bool = True,
    ) -> SupervisorDecision:
        if verification.get("sufficient"):
            return SupervisorDecision(
                action="finalize",
                stop_reason="sufficient",
                reason="La evidencia es suficiente y está verificada.",
            )
        if not allow_reinvestigation:
            return SupervisorDecision(
                action="finalize",
                stop_reason="reinvestigation_disabled",
                reason="Reinvestigación desactivada en esta configuración.",
            )
        if iteration >= self.max_iterations:
            return SupervisorDecision(
                action="finalize",
                stop_reason="max_iterations",
                reason=f"Se alcanzó el máximo de {self.max_iterations} iteraciones.",
            )
        if tracker.work_remaining < MIN_TOKENS_FOR_ITERATION:
            return SupervisorDecision(
                action="finalize",
                stop_reason="budget",
                reason="Presupuesto de tokens insuficiente para otra iteración.",
            )

        asked = {
            (_norm(t["question"]), t.get("transform_hint", "auto"))
            for t in tasks
        }
        asked_questions = {q for q, _ in asked}
        candidates: list[
            tuple[str, str, str, str | None]
        ] = []  # (pregunta, título, motivo, id_que_sustituye)
        for gap in analysis_notes.get("gaps", []):
            if _norm(gap) not in asked_questions:
                candidates.append((gap, "Vacío de información", "gap", None))
        for u in verification.get("uncovered", []):
            if (
                (_norm(u["question"]), "rag_fusion") not in asked
            ):  
                candidates.append(
                    (
                        u["question"],
                        "Reintento con más cobertura",
                        "uncovered",
                        u["id"],
                    )
                )
        new: list[SubTask] = []
        seen: set[str] = set()
        for question, title, reason, replaces in candidates:
            if _norm(question) in seen:
                continue
            seen.add(_norm(question))
            new.append(
                SubTask(
                    id=f"t{len(tasks) + len(new) + 1}",
                    title=title[:80],
                    question=question,
                    iteration=iteration + 1,
                    strategy_hint="hybrid",
                    transform_hint="rag_fusion"
                    if reason == "uncovered"
                    else "auto",
                    replaces=replaces,
                )
            )
            if len(new) >= self.settings.max_followup_tasks:
                break
        if not new:
            return SupervisorDecision(
                action="finalize",
                stop_reason="no_new_tasks",
                reason="No hay nuevas subtareas útiles que lanzar.",
            )
        return SupervisorDecision(
            action="continue",
            stop_reason="",
            reason=f"Evidencia insuficiente: se lanzan {len(new)} subtareas adicionales.",
            new_tasks=new,
        )
