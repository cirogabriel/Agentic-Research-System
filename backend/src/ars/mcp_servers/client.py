
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpClient:
    def __init__(self, server_module: str) -> None:
        # Se hereda el entorno 
        self.params = StdioServerParameters(
            command=sys.executable,
            args=["-m", server_module],
            env=dict(os.environ),
        )

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        async with (
            stdio_client(self.params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(name, arguments)
            if result.isError:
                raise RuntimeError(
                    f"Herramienta MCP '{name}' falló: {result.content}"
                )
            if getattr(result, "structuredContent", None):
                return dict(result.structuredContent)  
            text = next(
                (
                    c.text
                    for c in result.content
                    if getattr(c, "type", "") == "text"
                ),
                "{}",
            )
            return json.loads(text) 

    async def list_tools(self) -> list[str]:
        async with (
            stdio_client(self.params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            return [t.name for t in (await session.list_tools()).tools]

    def call_tool_sync(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
      
        return asyncio.run(self.call_tool(name, arguments))
