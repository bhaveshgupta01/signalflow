"""Base class for v3 specialist agents.

Each specialist has its own Gemini session, system prompt, and error budget.
Specialists write TradeProposals to the DB; they never see the wallet or
other agents' proposals.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from google import genai
from google.genai import types

from mcp_client import BobaClient

logger = logging.getLogger(__name__)


class BaseSpecialist:
    """Shared infrastructure for all v3 specialist agents.

    Subclasses implement:
      - ``AGENT_ID``: unique string identifier
      - ``SYSTEM_PROMPT``: role-specific instructions
      - ``MODEL``: Gemini model name (default flash-lite)
      - ``handle(event_data) -> list[dict]``: produce proposals from an event
    """

    AGENT_ID: str = "base"
    SYSTEM_PROMPT: str = ""
    MODEL: str = "gemini-2.5-flash-lite"
    MAX_TOOL_ROUNDS: int = 10
    TIMEOUT_SECONDS: float = 45.0

    def __init__(self, client: genai.Client, boba: BobaClient) -> None:
        self.client = client
        self.boba = boba
        self._gemini_tools: list[types.Tool] | None = None

    # ── Gemini tool helpers (shared) ─────────────────────────────────────────

    def _get_gemini_tools(self) -> list[types.Tool]:
        """Lazily build and cache Gemini-compatible tool declarations."""
        if self._gemini_tools is None:
            self._gemini_tools = _boba_tools_to_gemini(self.boba.tools_for_claude)
        return self._gemini_tools

    async def run_tool_loop(
        self,
        user_message: str,
        system_prompt: str | None = None,
        max_rounds: int | None = None,
    ) -> str:
        """Run a Gemini conversation with Boba tools until tool calls stop.

        Returns the final concatenated text response.
        """
        system = system_prompt or self.SYSTEM_PROMPT
        rounds = max_rounds or self.MAX_TOOL_ROUNDS
        gemini_tools = self._get_gemini_tools()

        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part(text=user_message)])
        ]
        text_parts: list[str] = []

        for _ in range(rounds):
            # Retry loop for rate limits (429)
            response = None
            for retry in range(4):
                try:
                    response = await asyncio.wait_for(
                        self.client.aio.models.generate_content(
                            model=self.MODEL,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                system_instruction=system,
                                tools=gemini_tools,
                                temperature=0.4,
                                max_output_tokens=4096,
                            ),
                        ),
                        timeout=self.TIMEOUT_SECONDS,
                    )
                    break
                except asyncio.TimeoutError:
                    logger.warning(
                        "[%s] Gemini timeout after %.0fs — returning partial",
                        self.AGENT_ID, self.TIMEOUT_SECONDS,
                    )
                    return "\n".join(text_parts) if text_parts else ""
                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        wait = (retry + 1) * 15
                        logger.warning(
                            "[%s] Rate limited (429) — waiting %ds (retry %d/3)",
                            self.AGENT_ID, wait, retry + 1,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise
            if response is None:
                logger.warning("[%s] Exhausted retries on rate limit", self.AGENT_ID)
                return "\n".join(text_parts) if text_parts else ""

            text_parts = []
            function_calls: list[types.FunctionCall] = []

            if not response.candidates:
                logger.warning("[%s] Gemini returned no candidates", self.AGENT_ID)
                return "\n".join(text_parts) if text_parts else ""

            for candidate in response.candidates:
                if not candidate.content or not candidate.content.parts:
                    continue
                for part in candidate.content.parts:
                    if part.text:
                        text_parts.append(part.text)
                    if part.function_call:
                        function_calls.append(part.function_call)

            if not function_calls:
                return "\n".join(text_parts)

            contents.append(candidate.content)

            function_responses = []
            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}
                logger.debug("[%s] Tool: %s(%s)", self.AGENT_ID, tool_name, str(tool_args)[:200])
                try:
                    result = await self.boba.call_tool(tool_name, tool_args)
                except Exception as e:
                    result = f"Error: {e}"
                function_responses.append(
                    types.Part(function_response=types.FunctionResponse(
                        name=tool_name,
                        response={"result": result},
                    ))
                )

            contents.append(types.Content(role="user", parts=function_responses))

        return "\n".join(text_parts) if text_parts else ""

    # ── JSON extraction (shared) ─────────────────────────────────────────────

    @staticmethod
    def extract_json(text: str) -> dict | list | None:
        """Extract the first JSON object or array from text."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start = text.find(start_char)
            if start == -1:
                continue
            depth = 0
            for i in range(start, len(text)):
                if text[i] == start_char:
                    depth += 1
                elif text[i] == end_char:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except json.JSONDecodeError:
                            break
        return None

    # ── Price helper (shared) ────────────────────────────────────────────────

    async def get_asset_price(self, asset: str) -> float:
        """Fetch current price from Hyperliquid."""
        try:
            raw = await self.boba.call_tool("hl_get_asset", {"coin": asset})
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, dict):
                mark = data.get("mark") or data.get("markPx") or data.get("price") or 0
                return float(str(mark).replace(",", ""))
        except Exception:
            logger.debug("[%s] Could not fetch price for %s", self.AGENT_ID, asset)
        try:
            raw = await self.boba.call_tool("hl_get_markets", {"search": asset, "limit": 1})
            data = json.loads(raw) if isinstance(raw, str) else raw
            assets = data.get("assets", [])
            if assets:
                return float(str(assets[0].get("mark", 0)).replace(",", ""))
        except Exception:
            pass
        return 0.0

    # ── Abstract interface ───────────────────────────────────────────────────

    async def handle(self, event_data: dict[str, Any]) -> list[dict]:
        """Process an event and return a list of proposal dicts.

        Each dict should match the TradeProposal schema:
          agent_id, asset, direction, conviction, edge_type,
          reasoning, suggested_risk_pct, timeframe_hours, invalidation
        """
        raise NotImplementedError


# ── Gemini tool conversion (module-level, shared across agents) ──────────────

def _clean_schema_for_gemini(schema: dict) -> dict:
    """Recursively clean a JSON Schema for Gemini compatibility."""
    if not isinstance(schema, dict):
        return schema
    cleaned: dict = {}
    prop_type = schema.get("type", "string")
    if isinstance(prop_type, str):
        cleaned["type"] = prop_type.upper()
    elif isinstance(prop_type, list):
        non_null = [t for t in prop_type if t != "null"]
        cleaned["type"] = (non_null[0] if non_null else "STRING").upper()
    if "description" in schema:
        cleaned["description"] = schema["description"]
    if "enum" in schema:
        cleaned["enum"] = schema["enum"]
    if cleaned.get("type") == "ARRAY":
        items = schema.get("items", {"type": "string"})
        cleaned["items"] = _clean_schema_for_gemini(items)
    if cleaned.get("type") == "OBJECT" and "properties" in schema:
        cleaned["properties"] = {
            k: _clean_schema_for_gemini(v) for k, v in schema["properties"].items()
        }
        if "required" in schema:
            cleaned["required"] = schema["required"]
    return cleaned


def _boba_tools_to_gemini(boba_tools: list[dict]) -> list[types.Tool]:
    """Convert Boba MCP tool definitions to Gemini function declarations."""
    declarations = []
    for tool in boba_tools:
        schema = tool.get("input_schema", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        clean_props = {k: _clean_schema_for_gemini(v) for k, v in properties.items()}
        decl = types.FunctionDeclaration(
            name=tool["name"],
            description=tool.get("description", ""),
            parameters={
                "type": "OBJECT",
                "properties": clean_props,
                "required": required,
            } if clean_props else None,
        )
        declarations.append(decl)
    return [types.Tool(function_declarations=declarations)]
