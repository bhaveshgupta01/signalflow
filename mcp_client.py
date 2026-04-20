"""Boba MCP connection — bridges Gemini to Polymarket + Hyperliquid.

Supports two connection modes:
  1. stdio: via local `boba mcp` command (needs proxy running)
  2. SSE: direct HTTP connection to Boba's remote MCP server (headless/server deployments)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.sse import sse_client

from config import BOBA_API_KEY

logger = logging.getLogger(__name__)

# Boba MCP remote server
BOBA_MCP_URL = "https://mcp-skunk.up.railway.app"
BOBA_AUTH_URL = "https://krakend-skunk.up.railway.app/v2"


def _find_boba_bin() -> str | None:
    """Find the boba binary on disk."""
    import glob
    patterns = [
        os.path.expanduser("~/.npm/_npx/*/node_modules/.bin/boba"),
        os.path.expanduser("~/.npm/_npx/*/node_modules/@tradeboba/cli-*/bin/boba"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    try:
        result = subprocess.run(["which", "boba"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


async def _get_boba_access_token() -> str | None:
    """Get access token from Boba config or auth endpoint."""
    # Try reading from local config (written by `boba login`)
    config_paths = [
        os.path.expanduser("~/.config/boba-cli/config.json"),
        os.path.expanduser("~/Library/Application Support/boba-cli/config.json"),
    ]
    for path in config_paths:
        try:
            with open(path) as f:
                config = json.load(f)
                token = config.get("tokens", {}).get("accessToken")
                if token:
                    return token
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            continue

    # Try authenticating via the auth endpoint
    agent_id = os.getenv("BOBA_AGENT_ID", "")
    agent_secret = os.getenv("BOBA_AGENT_SECRET", BOBA_API_KEY)
    if agent_id and agent_secret:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{BOBA_AUTH_URL}/auth/agent",
                    json={"agentId": agent_id, "secret": agent_secret},
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("accessToken", data.get("access_token"))
        except Exception as e:
            logger.debug("Auth endpoint failed: %s", e)

    return None


class BobaClient:
    """Manages a persistent MCP session with the Boba agent server.

    MCP stdio sessions are NOT safe for concurrent requests — sending two
    requests on the same pipe can deadlock. We use an asyncio.Lock to
    serialize all call_tool invocations.
    """

    def __init__(self) -> None:
        self.session: ClientSession | None = None
        self._tools: list[dict] | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._call_lock: asyncio.Lock = asyncio.Lock()

    async def connect(self) -> None:
        """Connect to Boba MCP — tries stdio first, falls back to SSE.

        SSE is attempted last because the hosted auth endpoint
        (krakend-skunk.up.railway.app/v2/auth/agent) currently returns 404
        and the cached config.json does not ship an accessToken — so SSE
        only works after an interactive `boba login`. Stdio via the local
        proxy is what actually works for this project today.
        """
        try:
            await self._connect_stdio()
            logger.info("Transport: stdio (via local boba proxy)")
            return
        except Exception as e:
            logger.warning("Stdio connection failed (%s), trying SSE...", e)

        await self._connect_sse()
        logger.info("Transport: SSE (direct to Boba cloud)")

    async def _connect_stdio(self) -> None:
        """Connect via local boba mcp command (requires proxy running)."""
        boba_bin = _find_boba_bin()
        if boba_bin and os.path.exists(boba_bin):
            command, args = boba_bin, ["mcp"]
        else:
            command, args = "npx", ["-y", "@tradeboba/cli@latest", "mcp"]

        logger.info("Trying stdio connection: %s %s", command, " ".join(args))

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
        await self._discover_tools()
        logger.info("Connected via stdio")

    async def _connect_sse(self) -> None:
        """Connect directly to Boba's remote MCP server via SSE."""
        token = await _get_boba_access_token()
        if not token:
            raise RuntimeError(
                "No Boba access token. Run 'boba login' or set BOBA_AGENT_ID + BOBA_AGENT_SECRET in .env"
            )

        logger.info("Connecting to Boba MCP via SSE: %s", BOBA_MCP_URL)

        headers = {"Authorization": f"Bearer {token}"}

        self._exit_stack = AsyncExitStack()
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            sse_client(f"{BOBA_MCP_URL}/sse", headers=headers)
        )
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()
        await self._discover_tools()
        logger.info("Connected via SSE")

    async def _discover_tools(self) -> None:
        """Discover available tools from the MCP session."""
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
        if self._tools is None:
            raise RuntimeError("Not connected — call connect() first")
        return self._tools

    async def call_tool(self, name: str, arguments: dict, timeout: float = 30.0) -> str:
        if self.session is None:
            raise RuntimeError("Not connected — call connect() first")
        async with self._call_lock:
            try:
                result = await asyncio.wait_for(
                    self.session.call_tool(name, arguments),
                    timeout=timeout,
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                logger.warning(
                    "Boba tool %s timed out after %.0fs — reconnecting session",
                    name, timeout,
                )
                # The stdio pipe is stuck. Reconnect to get a fresh pipe.
                await self._reconnect()
                raise TimeoutError(f"Boba tool {name} timed out after {timeout}s")
        parts: list[str] = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts) if parts else str(result.content)

    async def _reconnect(self) -> None:
        """Kill the stuck session and establish a fresh one."""
        logger.info("Boba: reconnecting stdio session...")
        try:
            if self._exit_stack:
                await self._exit_stack.aclose()
        except Exception:
            pass
        self._exit_stack = None
        self.session = None
        self._tools = None
        try:
            await self._connect_stdio()
            logger.info("Boba: reconnected successfully (%d tools)", len(self._tools or []))
        except Exception as e:
            logger.error("Boba: reconnection failed: %s", e)

    async def disconnect(self) -> None:
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self.session = None
            logger.info("Disconnected from Boba MCP server")
