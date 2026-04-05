"""Boba MCP connection — bridges Gemini to Polymarket + Hyperliquid."""

from __future__ import annotations

import logging
import os
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from config import BOBA_API_KEY

logger = logging.getLogger(__name__)

# Resolve the boba binary path
_BOBA_BIN = os.path.expanduser(
    "~/.npm/_npx/528a0913b9bfc11d/node_modules/.bin/boba"
)


class BobaClient:
    """Manages a persistent MCP session with the Boba agent server."""

    def __init__(self) -> None:
        self.session: ClientSession | None = None
        self._tools: list[dict] | None = None
        self._exit_stack: AsyncExitStack | None = None

    async def connect(self) -> None:
        """Start the Boba MCP server and initialise the session."""
        if os.path.exists(_BOBA_BIN):
            command, args = _BOBA_BIN, ["mcp"]
        else:
            command, args = "npx", ["-y", "@tradeboba/cli@latest", "mcp"]

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env={**os.environ, "BOBA_API_KEY": BOBA_API_KEY},
        )

        # Use AsyncExitStack to keep the stdio transport alive
        self._exit_stack = AsyncExitStack()
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()
        logger.info("Connected to Boba MCP server")

        # Discover available tools
        tools_result = await self.session.list_tools()
        self._tools = [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
            }
            for t in tools_result.tools
        ]
        logger.info("Discovered %d Boba tools", len(self._tools))

    @property
    def tools_for_claude(self) -> list[dict]:
        """Return tool definitions formatted for the LLM messages API."""
        if self._tools is None:
            raise RuntimeError("Not connected — call connect() first")
        return self._tools

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Invoke a Boba MCP tool and return the text result."""
        if self.session is None:
            raise RuntimeError("Not connected — call connect() first")

        result = await self.session.call_tool(name, arguments)
        parts: list[str] = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts) if parts else str(result.content)

    async def disconnect(self) -> None:
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self.session = None
            logger.info("Disconnected from Boba MCP server")
