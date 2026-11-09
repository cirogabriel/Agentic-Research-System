from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ResearchType = Literal[
    "explanatory", "comparative", "descriptive", "exploratory", "fact_finding"
]


class QueryUnderstanding(BaseModel):
  

    normalized_query: str = Field(
        description="Consulta corregida (ortografía/gramática) SIN cambiar la intención ni añadir supuestos"
    )
    topic: str
    objective: str
    research_type: ResearchType
    entities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(
        default_factory=list,
        description="Regiones, periodos, condiciones mencionadas explícitamente",
    )
    key_aspects: list[str] = Field(default_factory=list)
    is_ambiguous: bool = Field(
        description="True solo si es imposible investigar sin hacer suposiciones importantes"
    )
    clarification_questions: list[str] = Field(
        default_factory=list, description="Máximo 3, solo si is_ambiguous"
    )
    needs_research: bool = Field(
        description="False para saludos, charla o peticiones que no requieren documentos"
    )
    direct_answer: str | None = Field(
        default=None,
        description="Respuesta breve, solo si needs_research es False",
    )


class QueryAnalysis(QueryUnderstanding):

    language: str = "other"
    used_llm: bool = False
