
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage

from ars.agents.toolbox import DirectToolbox, McpToolbox, RetrievalToolbox
from ars.config import Settings
from ars.graph.builder import build_graph
from ars.graph.nodes import GraphDeps, GraphOptions
from ars.graph.reporter import MemoryReporter
from ars.llm.base import StructuredLLM
from ars.llm.budget import UsageTracker
from ars.llm.gateway import LLMGateway
from ars.logging_config import research_id_var
from ars.rag.retrieval import RetrievalService


def run_research(
    *,
    settings: Settings,
    query: str,
    options: GraphOptions,
    reporter: MemoryReporter,
    tracker: UsageTracker,
    thread_id: str,
    retrieval: RetrievalService | None = None,
    llm: StructuredLLM | None = None,
    toolbox: RetrievalToolbox | None = None,
    checkpointer: Any | None = None,
    parent_context: str = "",
    skip_clarification: bool = False,
    resume: bool = False,
    research_id: str = "",
) -> dict[str, Any]:
    research_id_var.set(research_id or thread_id)
    llm = llm or LLMGateway(settings, tracker)
    if toolbox is None:
        if settings.agent_tool_transport == "mcp":
            toolbox = McpToolbox(settings)
        else:
            assert retrieval is not None, (
                "Se requiere RetrievalService para el transporte directo"
            )
            toolbox = DirectToolbox(retrieval, llm, tracker)
    graph = build_graph(
        GraphDeps(settings, llm, tracker, toolbox, reporter, options),
        checkpointer,
    )
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.graph_recursion_limit,
        "max_concurrency": settings.max_parallel_workers,
    }
    if resume:
        return graph.invoke(None, config)  
    initial = {
        "research_id": research_id or thread_id,
        "query": query,
        "parent_context": parent_context,
        "skip_clarification": skip_clarification,
        "messages": [HumanMessage(content=query, name="user")],
        "iteration": 0,
        "errors": [],
    }
    return graph.invoke(initial, config)
