
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ars.schemas.rag import StrategyOrAuto, TransformOrAuto


# ---- Supervisor ---------------------------------------------------------------------------------
class PlannedTask(BaseModel):
    title: str = Field(description="Título corto del aspecto a investigar")
    question: str = Field(
        description="Pregunta autosuficiente para buscar en los documentos"
    )
    aspect: str | None = None
    strategy_hint: StrategyOrAuto = "auto"
    transform_hint: TransformOrAuto = "auto"


class ResearchPlan(BaseModel):
    rationale: str
    subtasks: list[PlannedTask]


class SubTask(BaseModel):
    id: str
    title: str
    question: str
    aspect: str | None = None
    strategy_hint: StrategyOrAuto = "auto"
    transform_hint: TransformOrAuto = "auto"
    iteration: int = 1
    replaces: str | None = (
        None  # id de la subtarea sin cobertura a la que sustituye este reintento
    )


class SupervisorDecision(BaseModel):
    action: Literal["continue", "finalize"]
    reason: str
    stop_reason: str = "sufficient"  # sufficient | max_iterations | budget | no_new_tasks | reinvestigation_disabled
    new_tasks: list[SubTask] = Field(default_factory=list)


# ---- Research ------------------------------------------
class EvidenceItem(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    page_number: int | None = None
    chunk_index: int
    text: str
    score: float


class TaskResult(BaseModel):
    task_id: str
    iteration: int
    strategy: str | None = None
    transform: str | None = None
    queries: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    error: str | None = None


# ---- Analysis -----------------------------------------------------------------------------------
class FindingDraft(BaseModel):
    statement: str
    kind: Literal["fact", "interpretation"] = "fact"
    evidence_labels: list[str] = Field(
        default_factory=list,
        description="Etiquetas S# de las evidencias que lo respaldan",
    )
    aspect: str | None = None


class Contradiction(BaseModel):
    topic: str
    positions: list[str]
    evidence_labels: list[str] = Field(default_factory=list)


class AnalysisOutput(BaseModel):
    findings: list[FindingDraft]
    agreements: list[str] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    gaps: list[str] = Field(
        default_factory=list,
        description="Información que falta para responder bien",
    )
    preliminary_conclusions: list[str] = Field(default_factory=list)


# ---- Verification ---------------------------------------------
class Verdict(BaseModel):
    id: str
    verdict: Literal[
        "supported", "partially_supported", "unsupported", "contradicted"
    ]
    note: str = ""


class VerificationVerdicts(BaseModel):
    verdicts: list[Verdict]


# ---- Report -------------------------------------------------------------------------------------
class ReportSection(BaseModel):
    heading: str
    body: str = Field(
        description="Markdown; cita fuentes con [S1], [S2]. Solo etiquetas que existan."
    )


class ReportDraft(BaseModel):
    title: str
    executive_summary: str
    objective: str
    sections: list[ReportSection]
    comparison: str | None = None
    conclusions: list[str]
    limitations: list[str] = Field(default_factory=list)


class BaselineAnswer(BaseModel):
   

    answer: str
