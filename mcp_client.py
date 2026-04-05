"""Boba MCP connection — bridges Gemini to Polymarket + Hyperliquid."""

from __future__ import annotations

import logging
import os
import subprocess
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from config import BOBA_API_KEY

logger = logging.getLogger(__name__)

# Try to find the boba binary
_BOBA_PATHS = [
    os.path.expanduser("~/.npm/_npx/528a0913b9bfc11d/node_modules/.bin/boba"),
    os.path.expanduser("~/.npm/_npx/*/node_modules/.bin/boba"),
]


def _find_boba_bin() -> str | None:
    """Find the boba binary on disk."""
    import glob
    for pattern in _BOBA_PATHS:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    # Check if it's in PATH
    try:
        result = subprocess.run(["which", "boba"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


class BobaClient:
    """Manages a persistent MCP session with the Boba agent server."""

    def __init__(self) -> None:
        self.session: ClientSession | None = None
        self._tools: list[dict] | None = None
        self._exit_stack: AsyncExitStack | None = None

    async def connect(self) -> None:
        """Start the Boba MCP server and initialise the session."""
        boba_bin = _find_boba_bin()
        if boba_bin and os.path.exists(boba_bin):
            command, args = boba_bin, ["mcp"]
            logger.info("Using boba binary: %s", boba_bin)
        else:
            command, args = "npx", ["-y", "@tradeboba/cli@latest", "mcp"]
            logger.info("Using npx to launch boba")

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env={**os.environ, "BOBA_API_KEY": BOBA_API_KEY},
        )

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
