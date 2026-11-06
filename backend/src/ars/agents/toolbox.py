"""Herramientas de recuperación disponibles para el Research Agent (lista cerrada: nada de ejecución de código).

Dos transportes con la misma interfaz:
  - DirectToolbox: llama al servicio Python en proceso (por defecto; sin sobrecarga).
  - McpToolbox:    llama al servidor MCP de recuperación (interoperabilidad; ver docs/MCP.md).
"""
from __future__ import annotations

from typing import Protocol

from ars.config import Settings
from ars.llm.base import StructuredLLM
from ars.llm.budget import ExecutionRecord, UsageTracker
from ars.rag.retrieval import RetrievalService
from ars.schemas.rag import RetrievalRequest, RetrievalResult, RoutingDecision, ScoredChunk


class RetrievalToolbox(Protocol):
    def retrieve(self, req: RetrievalRequest, rec: ExecutionRecord | None = None) -> RetrievalResult: ...


class DirectToolbox:
    def __init__(self, retrieval: RetrievalService, llm: StructuredLLM, tracker: UsageTracker) -> None:
        self.retrieval, self.llm, self.tracker = retrieval, llm, tracker

    def retrieve(self, req: RetrievalRequest, rec: ExecutionRecord | None = None) -> RetrievalResult:
        return self.retrieval.retrieve(req, llm=self.llm, tracker=self.tracker, rec=rec)


class McpToolbox:
    """Cliente MCP (stdio) hacia el Retrieval MCP Server. Cada llamada abre una sesión: es más lento que el
    transporte directo, pero demuestra cómo un agente consume herramientas expuestas por MCP."""

    def __init__(self, settings: Settings) -> None:
        from ars.mcp_servers.client import McpClient

        self.settings = settings
        self.client = McpClient("ars.mcp_servers.retrieval_server")

    def retrieve(self, req: RetrievalRequest, rec: ExecutionRecord | None = None) -> RetrievalResult:
        args = {
            "query": req.query, "top_k": req.top_k, "strategy": req.strategy,
            "transform": "none",  # el servidor MCP no dispone del LLM de la investigación: sin transformaciones de consulta
            "rerank": req.rerank if req.rerank is not None else self.settings.rerank_enabled,
            "document_ids": [str(d) for d in req.filters.document_ids] if req.filters and req.filters.document_ids else None,
        }
        data = self.client.call_tool_sync("get_relevant_chunks", args)
        chunks = [ScoredChunk(**c) for c in data.get("chunks", [])]
        if rec is not None:
            rec.tool_calls.append("mcp:get_relevant_chunks")
        return RetrievalResult(
            chunks=chunks, queries=[req.query], latency_ms=int(data.get("latency_ms", 0)), reranked=bool(data.get("reranked", False)),
            decision=RoutingDecision(strategy=data.get("strategy", "hybrid"), transform=data.get("transform", "none"), reason="resuelto por el servidor MCP"),
        )
