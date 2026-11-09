from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from ars.config import get_settings
from ars.logging_config import configure_logging
from ars.runtime import AppContainer
from ars.schemas.rag import ScoredChunk
from ars.mcp_servers.schemas import ChunkOut


def bootstrap() -> tuple[AppContainer, str]:

    settings = get_settings()
    configure_logging(
        settings.log_level, settings.log_json
    )  # a stderr: stdout pertenece al protocolo stdio
    container = AppContainer.from_settings(
        settings, with_checkpointer=False, with_runner=False
    )
    return container, os.getenv("MCP_TRANSPORT", settings.mcp_transport)


def make_server(name: str, instructions: str) -> FastMCP:
    s = get_settings()
    return FastMCP(
        name,
        instructions=instructions,
        host=s.mcp_host,
        port=int(os.getenv("MCP_PORT", s.mcp_port)),
    )


def to_chunk_out(c: ScoredChunk) -> ChunkOut:
    return ChunkOut(
        chunk_id=str(c.chunk_id),
        document_id=str(c.document_id),
        document_name=c.document_name,
        page_number=c.page_number,
        chunk_index=c.chunk_index,
        content=c.content,
        score=round(c.score, 5),
        source=c.source,
    )


def run(server: FastMCP, transport: str) -> None:
    logging.getLogger(__name__).info(
        "Iniciando servidor MCP %s (%s)", server.name, transport
    )
    server.run(transport=transport)  
