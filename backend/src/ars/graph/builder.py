"""Ensamblado del StateGraph (Supervisor–Worker)."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START
from langgraph.graph import StateGraph

from ars.graph.nodes import GraphDeps, ResearchNodes
from ars.graph.state import ResearchState


def build_graph(deps: GraphDeps, checkpointer: Any | None = None) -> Any:
    """
        START → understand ─┬─ (aclaración / respuesta directa / error) → END
                            └→ plan ──(Send × N)──► research_worker ─► analyze ─► verify ─► decide
                                                          ▲                                  │
                                                          └────────(Send × M, reinvestigar)──┤
                                                                                             └→ report → final_evaluation → END
    """
    n = ResearchNodes(deps)
    g = StateGraph(ResearchState)
    g.add_node("understand", n.understand)
    g.add_node("plan", n.plan)
    g.add_node("research_worker", n.research_worker)
    g.add_node("analyze", n.analyze)
    g.add_node("verify", n.verify)
    g.add_node("decide", n.decide)
    g.add_node("report", n.report)
    g.add_node("final_evaluation", n.final_evaluation)

    g.add_edge(START, "understand")
    g.add_conditional_edges("understand", n.route_after_understand, {"plan": "plan", "end": END})
    g.add_conditional_edges("plan", n.fan_out, ["research_worker", END])
    g.add_edge("research_worker", "analyze")  # LangGraph espera a TODOS los workers del superpaso antes de analizar
    g.add_edge("analyze", "verify")
    g.add_edge("verify", "decide")
    g.add_conditional_edges("decide", n.route_after_decide, ["research_worker", "report"])
    g.add_edge("report", "final_evaluation")
    g.add_edge("final_evaluation", END)
    return g.compile(checkpointer=checkpointer)
