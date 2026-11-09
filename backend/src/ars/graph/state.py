
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from ars.agents.evidence import merge_sources


class ResearchState(TypedDict, total=False):
    # entrada
    research_id: str
    query: str
    parent_context: str
    skip_clarification: bool
    messages: Annotated[list[AnyMessage], add_messages]
    # trabajo
    analysis: dict[str, Any]
    iteration: int
    pending: list[dict[str, Any]]
    tasks: Annotated[
        list[dict[str, Any]], operator.add
    ]  # todas las subtareas 
    task_results: Annotated[
        list[dict[str, Any]], operator.add
    ]  # llegan en paralelo desde los workers
    sources: Annotated[dict[str, dict[str, Any]], merge_sources]
    findings: list[dict[str, Any]]
    analysis_notes: dict[str, Any]
    analysis_failed: bool
    verification: dict[str, Any]
    decision: dict[str, Any]
    budget_exhausted: bool
    # salida
    report: dict[str, Any]
    quality: dict[str, Any]
    status: str
    stop_reason: str
    errors: Annotated[list[str], operator.add]
    failed: bool


class WorkerInput(TypedDict):
 

    tasks: list[dict[str, Any]]
    iteration: int
