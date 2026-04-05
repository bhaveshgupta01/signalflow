"""Core agent loop — Gemini analyses signals and executes trades via Boba MCP.

Pipeline per cycle:
  1. SCAN   — signals.py detects Polymarket moves (no LLM)
  2. ANALYZE — Gemini + Boba tools → conviction score
  3. RISK    — risk.py enforces hard limits (no LLM)
  4. EXECUTE — Gemini + Boba tools → open perps position
  5. MANAGE  — Gemini checks open positions each cycle
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

from google import genai
from google.genai import types

from config import (
    GEMINI_MODEL, CONVICTION_THRESHOLD, KOL_SIGNAL_BOOST,
    PAPER_WALLET_STARTING_BALANCE, MAX_POSITION_AGE_HOURS,
)
from db import (
    get_open_positions,
    get_stats,
    save_analysis,
    save_decision,
    save_position,
    save_position_snapshot,
    save_signal,
    save_wallet_snapshot,
    update_position,
)
from event_bus import Event, TriggerType
from mcp_client import BobaClient
from models import (
    AgentDecision,
    Analysis,
    Direction,
    Position,
    PositionSnapshot,
    PositionStatus,
    Signal,
    WalletSnapshot,
)
from risk import (
    calculate_position_size,
    can_open_position,
    can_open_position_for_asset,
    clamp_leverage,
    compute_stop_take,
)
from kol_tracker import check_kol_alignment, detect_kol_signals
from signals import detect_signals

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are SignalFlow, an aggressive AI crypto trading agent. You have $100 to \
exploit any edge you can find. You trade perpetual futures on Hyperliquid.

## Your job
You receive market signals — prediction market moves, whale trades, funding \
rate spikes, or trending tokens. Your job is to find the trade and size it.

1. Use tools to gather data:
   - Polymarket sentiment, holders, price history
   - Hyperliquid price, funding rates, order book depth
   - Any other data that helps you decide

2. Decide: is there an edge? If yes, trade it aggressively.
   - High conviction = big position. Low conviction = small position or skip.
   - Think in hours, not days. We close positions within 4 hours.

3. Return JSON (no markdown fences):
{
  "conviction": <float 0.0–1.0>,
  "direction": "long" | "short",
  "asset": "<BTC, ETH, SOL, etc — must be on Hyperliquid>",
  "suggested_size_usd": <float — be aggressive, size based on conviction>,
  "leverage": <int 1-5>,
  "reasoning": "<2-3 sentences — what's the edge and why now>",
  "risk_notes": "<what could go wrong>"
}

## Rules
- Be aggressive. You're here to make money, not sit on cash.
- If conviction > 0.6, trade it. Size proportionally.
- suggested_size_usd should reflect your confidence: 0.6 conviction = $30-50, 0.9 conviction = $80-150.
- Only suggest assets on Hyperliquid perps (BTC, ETH, SOL, DOGE, ARB, etc.)
- Explain the edge clearly.
"""

TRADE_PROMPT = """\
Execute this trade on Hyperliquid using the available tools:
- Direction: {direction}
- Asset: {asset}
- Size: ${size_usd:.0f}
- Leverage: {leverage}x

After opening the position, also set:
- Stop-loss at ${stop_loss:.2f}
- Take-profit at ${take_profit:.2f}

Confirm the trade details when done.
"""

MANAGE_PROMPT = """\
You are managing open SignalFlow positions. For each position below, use the \
available tools to check current prices and PnL on Hyperliquid.

Open positions:
{positions_json}

For each position, decide:
- HOLD: if the trade thesis is still valid
- CLOSE: if the thesis has changed or risk/reward is no longer favorable

Return a JSON array:
[{{"position_id": <int>, "action": "hold" | "close", "reason": "<brief>"}}]
"""


def _clean_schema_for_gemini(schema: dict) -> dict:
    """Recursively clean a JSON Schema for Gemini compatibility."""
    if not isinstance(schema, dict):
        return schema

    cleaned: dict = {}
    prop_type = schema.get("type", "string")

    # Gemini expects uppercase types
    if isinstance(prop_type, str):
        cleaned["type"] = prop_type.upper()
    elif isinstance(prop_type, list):
        # Handle union types like ["string", "null"] — pick the first non-null
        non_null = [t for t in prop_type if t != "null"]
        cleaned["type"] = (non_null[0] if non_null else "STRING").upper()

    if "description" in schema:
        cleaned["description"] = schema["description"]
    if "enum" in schema:
        cleaned["enum"] = schema["enum"]

    # Handle array items — Gemini requires `items` for ARRAY types
    if cleaned.get("type") == "ARRAY":
        items = schema.get("items", {"type": "string"})
        cleaned["items"] = _clean_schema_for_gemini(items)

    # Handle object properties
    if cleaned.get("type") == "OBJECT" and "properties" in schema:
        cleaned["properties"] = {
            k: _clean_schema_for_gemini(v)
            for k, v in schema["properties"].items()
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

        clean_props = {
            k: _clean_schema_for_gemini(v) for k, v in properties.items()
        }

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


async def run_cycle(client: genai.Client, boba: BobaClient) -> AgentDecision:
    """Run one complete agent cycle: scan → analyze → risk → execute → manage."""
    cycle_id = uuid.uuid4().hex[:8]
    logger.info("── Cycle %s started ──", cycle_id)

    decision = AgentDecision(
        cycle_id=cycle_id,
        timestamp=datetime.utcnow(),
    )

    # ── Phase 1: Signal Detection (no LLM) ────────────────────────────────
    signals = await detect_signals(boba)
    decision.signals_detected = len(signals)
    logger.info("Detected %d signals", len(signals))

    # ── Phase 1b: KOL Whale Tracking (no LLM) ────────────────────────────
    kol_signals = await detect_kol_signals(boba)
    logger.info("Detected %d KOL signals", len(kol_signals))

    # ── Phase 2 & 3 & 4: Analyze, Risk-check, Execute ────────────────────
    for signal in signals:
        analysis = await _analyze_signal(client, boba, signal)
        if analysis is None:
            continue
        decision.analyses_produced += 1

        # KOL conviction boost: if a whale traded the same asset in same direction
        kol_matches = check_kol_alignment(
            analysis.suggested_asset, analysis.suggested_direction, minutes=60
        )
        if kol_matches:
            original = analysis.conviction_score
            analysis.conviction_score = min(1.0, analysis.conviction_score + KOL_SIGNAL_BOOST)
            kol_names = ", ".join(k.kol_name for k in kol_matches[:3])
            analysis.reasoning += (
                f" [KOL BOOST +{KOL_SIGNAL_BOOST:.0%}: {kol_names} "
                f"also went {analysis.suggested_direction.value} on {analysis.suggested_asset}]"
            )
            logger.info(
                "KOL boost: %.2f → %.2f (aligned with %s)",
                original, analysis.conviction_score, kol_names,
            )

        if analysis.conviction_score < CONVICTION_THRESHOLD:
            logger.info(
                "Low conviction (%.2f) for %s — skipping",
                analysis.conviction_score, signal.market_question,
            )
            continue

        # Risk gate
        allowed, reason = can_open_position(analysis.suggested_size_usd, 3)
        if not allowed:
            logger.warning("Risk blocked: %s", reason)
            continue
        allowed, reason = can_open_position_for_asset(
            analysis.suggested_asset, analysis.suggested_direction
        )
        if not allowed:
            logger.warning("Risk blocked: %s", reason)
            continue

        # Size and execute
        final_size = calculate_position_size(
            analysis.conviction_score, analysis.suggested_size_usd
        )
        position = await _execute_trade(client, boba, analysis, final_size)
        if position is not None:
            decision.trades_executed += 1

    # ── Phase 5: Manage open positions ────────────────────────────────────
    await _manage_positions(client, boba)

    # ── Save decision summary ─────────────────────────────────────────────
    decision.reasoning_summary = (
        f"Signals: {decision.signals_detected}, "
        f"Analyses: {decision.analyses_produced}, "
        f"Trades: {decision.trades_executed}"
    )
    save_decision(decision)
    logger.info("── Cycle %s complete: %s ──", cycle_id, decision.reasoning_summary)

    _save_snapshot()

    return decision


def _save_snapshot():
    """Record current wallet state for the portfolio growth chart."""
    stats = get_stats()
    save_wallet_snapshot(WalletSnapshot(
        balance=PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"],
        total_pnl=stats["total_pnl"],
        open_positions=len(get_open_positions()),
    ))


# ── Phase 2: LLM Analysis ────────────────────────────────────────────────────

async def _analyze_signal(
    client: genai.Client,
    boba: BobaClient,
    signal: Signal,
) -> Analysis | None:
    """Ask Gemini to analyse a signal using Boba market-data tools."""

    # Fetch Polymarket sentiment data for richer analysis
    sentiment_context = ""
    try:
        # Get top holders — shows if whales are positioning
        holders_raw = await boba.call_tool("pm_get_top_holders", {"conditionId": signal.market_id})
        holders_data = json.loads(holders_raw) if isinstance(holders_raw, str) else holders_raw
        holder_count = len(holders_data) if isinstance(holders_data, list) else 0
        sentiment_context += f"\nPolymarket top holders: {holder_count} large positions detected."
    except Exception:
        pass

    try:
        # Get community comments — crowd sentiment
        comments_raw = await boba.call_tool("pm_get_comments", {"eventId": signal.market_id, "limit": 15})
        comments_data = json.loads(comments_raw) if isinstance(comments_raw, str) else comments_raw
        comment_list = comments_data if isinstance(comments_data, list) else comments_data.get("comments", [])
        comment_count = len(comment_list)
        sentiment_context += f"\nPolymarket community: {comment_count} recent comments on this event."
    except Exception:
        pass

    # Help Gemini interpret the signal correctly
    # "Will BTC dip to $50k?" at price 0.08 means 8% chance of dip = BULLISH for BTC
    # "Will BTC reach $80k?" at price 0.90 means 90% chance of reaching = BULLISH for BTC
    interpretation_hint = ""
    q = signal.market_question.lower()
    if "dip" in q or "drop" in q or "fall" in q or "below" in q:
        if signal.price_change_pct < 0:
            interpretation_hint = (
                "IMPORTANT: This is a 'dip/drop' market and its probability FELL. "
                "That means the market thinks a dip is LESS likely now = BULLISH for the asset."
            )
        else:
            interpretation_hint = (
                "IMPORTANT: This is a 'dip/drop' market and its probability ROSE. "
                "That means the market thinks a dip is MORE likely = BEARISH for the asset."
            )
    elif "above" in q or "reach" in q or "rise" in q:
        if signal.price_change_pct > 0:
            interpretation_hint = (
                "IMPORTANT: This is a 'reach/above' market and its probability ROSE. "
                "That means the market is MORE bullish = BULLISH for the asset."
            )
        else:
            interpretation_hint = (
                "IMPORTANT: This is a 'reach/above' market and its probability FELL. "
                "That means the market is LESS bullish = BEARISH for the asset."
            )

    user_msg = (
        f"Analyze this prediction market signal:\n"
        f"- Market: {signal.market_question}\n"
        f"- Price moved {signal.price_change_pct:+.1%} in {signal.timeframe_minutes} minutes\n"
        f"- Current price/probability: {signal.current_price:.3f}\n"
        f"- Category: {signal.category}\n"
        f"{interpretation_hint}\n"
        f"{sentiment_context}\n\n"
        f"Use the tools to gather Hyperliquid and Polymarket data, then return your JSON analysis."
    )

    try:
        result_text = await _run_tool_loop(client, boba, SYSTEM_PROMPT, user_msg)
        parsed = _extract_json(result_text)
        if parsed is None:
            logger.warning("Could not parse analysis JSON from Gemini response")
            return None

        leverage = clamp_leverage(int(parsed.get("leverage", 3)))
        analysis = Analysis(
            signal_id=signal.id or 0,
            reasoning=parsed.get("reasoning", ""),
            conviction_score=float(parsed.get("conviction", 0)),
            suggested_direction=Direction(parsed.get("direction", "long")),
            suggested_asset=parsed.get("asset", "BTC"),
            suggested_size_usd=float(parsed.get("suggested_size_usd", 100)),
            risk_notes=parsed.get("risk_notes", f"leverage={leverage}"),
        )
        analysis = save_analysis(analysis)
        logger.info(
            "Analysis: %s %s conviction=%.2f asset=%s",
            analysis.suggested_direction.value,
            signal.market_question[:50],
            analysis.conviction_score,
            analysis.suggested_asset,
        )
        return analysis
    except Exception:
        logger.exception("Analysis failed for signal %s", signal.market_id)
        return None


# ── Phase 4: Trade Execution ─────────────────────────────────────────────────

async def _execute_trade(
    client: genai.Client,
    boba: BobaClient,
    analysis: Analysis,
    size_usd: float,
) -> Position | None:
    """Open a perps position via direct Boba hl_place_order, with Gemini fallback."""
    # Extract leverage from risk_notes (stashed there since Pydantic won't allow extra fields)
    leverage = 3
    if analysis.risk_notes and "leverage=" in analysis.risk_notes:
        try:
            leverage = int(analysis.risk_notes.split("leverage=")[1].split()[0].strip(","))
        except (ValueError, IndexError):
            pass
    leverage = clamp_leverage(leverage)

    # Get a rough entry price for stop/TP calculation
    entry_price = await _get_asset_price(boba, analysis.suggested_asset)
    if entry_price <= 0:
        logger.warning("Could not fetch entry price for %s", analysis.suggested_asset)
        return None

    stop_loss, take_profit = compute_stop_take(
        entry_price, analysis.suggested_direction
    )

    # Enrich analysis with token info (if available)
    try:
        info = await boba.call_tool("get_token_info", {"token": analysis.suggested_asset, "chain": "1"})
        logger.debug("Token info for %s: %s", analysis.suggested_asset, str(info)[:200])
    except Exception:
        pass

    # Direct execution via Boba — no Gemini in the loop
    try:
        side = "buy" if analysis.suggested_direction == Direction.LONG else "sell"

        # Set leverage first
        await boba.call_tool("hl_update_leverage", {
            "coin": analysis.suggested_asset,
            "leverage": leverage,
            "mode": "cross",
        })

        # Place the order
        order_result = await boba.call_tool("hl_place_order", {
            "coin": analysis.suggested_asset,
            "side": side,
            "size": size_usd,
            "type": "market",
        })
        logger.info("hl_place_order result: %s", str(order_result)[:200])

        # Set stop-loss
        sl_side = "sell" if analysis.suggested_direction == Direction.LONG else "buy"
        await boba.call_tool("hl_place_order", {
            "coin": analysis.suggested_asset,
            "side": sl_side,
            "size": size_usd,
            "type": "stop",
            "triggerPrice": str(stop_loss),
        })

        # Set take-profit
        await boba.call_tool("hl_place_order", {
            "coin": analysis.suggested_asset,
            "side": sl_side,
            "size": size_usd,
            "type": "take_profit",
            "triggerPrice": str(take_profit),
        })

        position = Position(
            analysis_id=analysis.id or 0,
            asset=analysis.suggested_asset,
            direction=analysis.suggested_direction,
            entry_price=entry_price,
            size_usd=size_usd,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        position = save_position(position)
        logger.info(
            "Opened %s %s $%.0f @ %.2f via hl_place_order",
            position.direction.value, position.asset,
            position.size_usd, position.entry_price,
        )
        return position
    except Exception:
        logger.exception("Direct trade execution failed for %s", analysis.suggested_asset)

    # Fallback: try via Gemini tool loop
    try:
        prompt = TRADE_PROMPT.format(
            direction=analysis.suggested_direction.value,
            asset=analysis.suggested_asset,
            size_usd=size_usd,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        await _run_tool_loop(client, boba, SYSTEM_PROMPT, prompt)

        position = Position(
            analysis_id=analysis.id or 0,
            asset=analysis.suggested_asset,
            direction=analysis.suggested_direction,
            entry_price=entry_price,
            size_usd=size_usd,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        position = save_position(position)
        logger.info(
            "Opened %s %s $%.0f @ %.2f via Gemini fallback (SL: %.2f, TP: %.2f)",
            position.direction.value, position.asset, position.size_usd,
            position.entry_price, position.stop_loss, position.take_profit,
        )
        return position
    except Exception:
        logger.exception("Gemini fallback trade execution also failed for %s", analysis.suggested_asset)
        return None


# ── Phase 5: Position Management ─────────────────────────────────────────────

async def _manage_positions(
    client: genai.Client,
    boba: BobaClient,
) -> None:
    """Smart position management — SL/TP, trailing stops, and AI-driven exit decisions."""
    open_pos = get_open_positions()
    if not open_pos:
        return

    now = datetime.utcnow()

    for p in open_pos:
        current_price = await _get_asset_price(boba, p.asset)
        if current_price <= 0:
            continue

        # Calculate PnL
        if p.direction == Direction.LONG:
            pnl = (current_price - p.entry_price) / p.entry_price * p.size_usd * p.leverage
        else:
            pnl = (p.entry_price - current_price) / p.entry_price * p.size_usd * p.leverage
        pnl = round(pnl, 2)
        pnl_pct = pnl / p.size_usd * 100 if p.size_usd > 0 else 0

        update_position(p.id, pnl=pnl)
        save_position_snapshot(PositionSnapshot(
            position_id=p.id, asset=p.asset,
            current_price=current_price, unrealized_pnl=pnl,
        ))

        age_hours = (now - p.opened_at).total_seconds() / 3600
        logger.info(
            "#%d %s %s: $%.2f -> $%.2f PnL=$%+.2f %.1f%% (%.1fh)",
            p.id, p.direction.value, p.asset, p.entry_price, current_price, pnl, pnl_pct, age_hours,
        )

        # ── Hard stop-loss: always respected, no AI override ──
        hit_sl = (p.direction == Direction.LONG and current_price <= p.stop_loss) or \
                 (p.direction == Direction.SHORT and current_price >= p.stop_loss)
        if hit_sl:
            update_position(p.id, status=PositionStatus.STOPPED, pnl=pnl, closed_at=now)
            logger.info("STOP #%d %s @ $%.2f -> PnL $%+.2f", p.id, p.asset, current_price, pnl)
            continue

        # ── Hard take-profit: always respected ──
        hit_tp = (p.direction == Direction.LONG and current_price >= p.take_profit) or \
                 (p.direction == Direction.SHORT and current_price <= p.take_profit)
        if hit_tp:
            update_position(p.id, status=PositionStatus.CLOSED, pnl=pnl, closed_at=now)
            logger.info("TP #%d %s @ $%.2f -> PnL $%+.2f", p.id, p.asset, current_price, pnl)
            continue

        # ── Trailing stop: profit > 5% -> lock in break-even ──
        if pnl_pct > 5.0:
            if p.direction == Direction.LONG and p.stop_loss < p.entry_price:
                new_sl = p.entry_price * 1.005
                update_position(p.id, stop_loss=new_sl)
                logger.info("TRAIL #%d %s SL -> $%.2f (locked)", p.id, p.asset, new_sl)
            elif p.direction == Direction.SHORT and p.stop_loss > p.entry_price:
                new_sl = p.entry_price * 0.995
                update_position(p.id, stop_loss=new_sl)
                logger.info("TRAIL #%d %s SL -> $%.2f (locked)", p.id, p.asset, new_sl)

        # ── Smart exit analysis: ask Gemini every ~30 min if position is old enough ──
        # Only for positions > 1 hour old, and only check once per ~30 min
        # (we check based on age being near a 30-min boundary to avoid spamming)
        age_minutes = age_hours * 60
        should_analyze_exit = (
            age_hours >= 1.0
            and int(age_minutes) % 30 < 2  # within 2 min of a 30-min mark
        )

        if should_analyze_exit:
            try:
                close_decision = await _should_close_position(client, boba, p, current_price, pnl, pnl_pct, age_hours)
                if close_decision:
                    status = PositionStatus.CLOSED if pnl >= 0 else PositionStatus.STOPPED
                    update_position(p.id, status=status, pnl=pnl, closed_at=now)
                    logger.info("AI-EXIT #%d %s %s -> PnL $%+.2f (%.1fh) reason: %s",
                                p.id, p.direction.value, p.asset, pnl, age_hours, close_decision)
                    continue
            except Exception:
                logger.debug("Exit analysis failed for #%d, continuing", p.id)

        # ── Hard age limit: 6 hours absolute max (safety net) ──
        if age_hours >= 6.0:
            status = PositionStatus.CLOSED if pnl >= 0 else PositionStatus.STOPPED
            update_position(p.id, status=status, pnl=pnl, closed_at=now)
            logger.info("MAX-AGE #%d %s after %.1fh -> PnL $%+.2f", p.id, p.asset, age_hours, pnl)


async def _should_close_position(
    client: genai.Client,
    boba: BobaClient,
    position: Position,
    current_price: float,
    pnl: float,
    pnl_pct: float,
    age_hours: float,
) -> str | None:
    """Ask Gemini whether to close a position. Returns reason string if yes, None if hold."""
    prompt = (
        f"You have an open {position.direction.value.upper()} position on {position.asset}:\n"
        f"- Entry: ${position.entry_price:,.2f}, Current: ${current_price:,.2f}\n"
        f"- PnL: ${pnl:+.2f} ({pnl_pct:+.1f}%)\n"
        f"- Size: ${position.size_usd:.0f} at {position.leverage}x leverage\n"
        f"- Age: {age_hours:.1f} hours\n"
        f"- Stop-loss: ${position.stop_loss:,.2f}, Take-profit: ${position.take_profit:,.2f}\n\n"
        f"Check the current market conditions using tools. Should you CLOSE this position now or HOLD?\n\n"
        f"Consider:\n"
        f"- Is the trend still in your favor?\n"
        f"- Are there signs of reversal?\n"
        f"- Is the risk/reward still good given the current PnL?\n"
        f"- Has the original thesis changed?\n\n"
        f"Return JSON: {{\"action\": \"close\" or \"hold\", \"reason\": \"one sentence why\"}}"
    )

    try:
        result = await _run_tool_loop(client, boba, SYSTEM_PROMPT, prompt, max_rounds=3)
        parsed = _extract_json(result)
        if parsed and isinstance(parsed, dict):
            action = parsed.get("action", "hold").lower()
            reason = parsed.get("reason", "")
            if action == "close":
                return reason or "AI decided to close"
    except Exception:
        pass
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run_tool_loop(
    client: genai.Client,
    boba: BobaClient,
    system: str,
    user_message: str,
    max_rounds: int = 10,
) -> str:
    """Run a Gemini conversation with Boba tools until Gemini stops calling tools.

    Returns the final text response.
    """
    gemini_tools = _boba_tools_to_gemini(boba.tools_for_claude)
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=user_message)])
    ]

    text_parts: list[str] = []

    for _ in range(max_rounds):
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        tools=gemini_tools,
                        temperature=0.4,
                        max_output_tokens=4096,
                    ),
                ),
                timeout=45.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Gemini API timeout after 45s — returning partial results")
            return "\n".join(text_parts) if text_parts else ""

        # Collect text and function calls from the response
        text_parts = []
        function_calls: list[types.FunctionCall] = []

        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.text:
                    text_parts.append(part.text)
                if part.function_call:
                    function_calls.append(part.function_call)

        # If no function calls, we're done
        if not function_calls:
            return "\n".join(text_parts)

        # Append the model's response to conversation history
        contents.append(candidate.content)

        # Execute each function call and build responses
        function_responses = []
        for fc in function_calls:
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}
            logger.debug("Tool call: %s(%s)", tool_name, json.dumps(tool_args)[:200])

            try:
                result = await boba.call_tool(tool_name, tool_args)
            except Exception as e:
                result = f"Error: {e}"

            function_responses.append(
                types.Part(function_response=types.FunctionResponse(
                    name=tool_name,
                    response={"result": result},
                ))
            )

        # Add tool results to conversation
        contents.append(types.Content(role="user", parts=function_responses))

    # Exhausted rounds — return whatever we have
    return "\n".join(text_parts) if text_parts else ""


async def _get_asset_price(boba: BobaClient, asset: str) -> float:
    """Fetch current price from Hyperliquid via Boba hl_get_asset tool."""
    try:
        raw = await boba.call_tool("hl_get_asset", {"coin": asset})
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, dict):
            mark = data.get("mark") or data.get("markPx") or data.get("price") or 0
            return float(str(mark).replace(",", ""))
    except Exception:
        logger.debug("Could not fetch price for %s via hl_get_asset", asset)

    # Fallback: try hl_get_markets with search
    try:
        raw = await boba.call_tool("hl_get_markets", {"search": asset, "limit": 1})
        data = json.loads(raw) if isinstance(raw, str) else raw
        assets = data.get("assets", [])
        if assets:
            mark = assets[0].get("mark", 0)
            return float(str(mark).replace(",", ""))
    except Exception:
        pass

    return 0.0


def _extract_json(text: str) -> dict | list | None:
    """Extract the first JSON object or array from text."""
    # Try the whole text first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try to find JSON within the text
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        # Find matching closing bracket
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


# ── Event-Driven Entry Point ────────────────────────────────────────────────


async def handle_event(client: genai.Client, boba: BobaClient, event: Event) -> None:
    """Dispatch an event to the appropriate handler."""
    cycle_id = uuid.uuid4().hex[:8]
    decision = AgentDecision(cycle_id=cycle_id, timestamp=datetime.utcnow())
    trade_opened = False

    if event.trigger == TriggerType.POLYMARKET_MOVE:
        signal = event.data["signal"]
        decision.signals_detected = 1
        position = await _process_signal(client, boba, signal)
        if position is not None:
            decision.trades_executed = 1
            decision.analyses_produced = 1
            trade_opened = True
        elif signal:
            # Signal was analyzed but didn't result in a trade
            decision.analyses_produced = 1

    elif event.trigger == TriggerType.KOL_WHALE_TRADE:
        kol_signal = event.data["kol_signal"]
        logger.info(
            "KOL event: %s %s %s $%.0f",
            kol_signal.kol_name,
            kol_signal.direction.value,
            kol_signal.asset,
            kol_signal.trade_size_usd,
        )

    elif event.trigger == TriggerType.FUNDING_RATE_SPIKE:
        asset = event.data["asset"]
        diff = event.data["diff"]
        hl_rate = event.data.get("hl_rate", 0)
        logger.info("Funding spike: %s diff=%.4f%% (HL=%.4f%%)", asset, diff * 100, hl_rate * 100)
        # Trade funding rate spikes: if HL funding is very positive, go short (longs are paying)
        # If HL funding is very negative, go long (shorts are paying)
        if abs(diff) > 0.0005:  # Only trade significant deviations (>0.05%)
            direction = Direction.SHORT if hl_rate > 0 else Direction.LONG
            synthetic_signal = Signal(
                market_id=f"funding_{asset}_{cycle_id}",
                market_question=f"Funding rate arbitrage: {asset} HL rate {hl_rate*100:.4f}%",
                current_price=0.5,
                price_change_pct=diff,
                timeframe_minutes=120,
                category="funding",
            )
            synthetic_signal = save_signal(synthetic_signal)
            decision.signals_detected = 1
            # Check risk before creating a synthetic analysis
            allowed, _ = can_open_position(100, 3)
            allowed_asset, _ = can_open_position_for_asset(asset, direction)
            if allowed and allowed_asset:
                analysis = Analysis(
                    signal_id=synthetic_signal.id or 0,
                    reasoning=f"Funding rate arbitrage: {asset} has {hl_rate*100:.4f}% HL funding vs market. Going {direction.value} to capture funding payments.",
                    conviction_score=min(0.85, 0.6 + abs(diff) * 100),
                    suggested_direction=direction,
                    suggested_asset=asset,
                    suggested_size_usd=80.0,
                    risk_notes=f"Funding can revert quickly. Rate diff: {diff*100:.4f}%",
                )
                analysis = save_analysis(analysis)
                decision.analyses_produced = 1
                if analysis.conviction_score >= CONVICTION_THRESHOLD:
                    final_size = calculate_position_size(analysis.conviction_score, analysis.suggested_size_usd)
                    position = await _execute_trade(client, boba, analysis, final_size)
                    if position:
                        decision.trades_executed = 1
                        trade_opened = True

    elif event.trigger == TriggerType.TOKEN_DISCOVERY:
        symbol = event.data.get("symbol", "")
        change = event.data.get("price_change_24h", 0)
        volume = event.data.get("volume_24h", 0)
        logger.info("Token discovery: %s +%.0f%% vol $%.0f", symbol, change * 100, volume)
        decision.signals_detected = 1

    elif event.trigger == TriggerType.CROSS_CHAIN_OPPORTUNITY:
        logger.info("Cross-chain opportunity: %s %s vs %s diff=%.2f%%",
                     event.data.get("asset"),
                     event.data.get("chain_a"),
                     event.data.get("chain_b"),
                     event.data.get("diff_pct", 0) * 100)

    elif event.trigger == TriggerType.PORTFOLIO_UPDATE:
        portfolio = event.data.get("portfolio", {})
        logger.info("Portfolio update: %s", str(portfolio)[:200])

    # Always update open positions PnL and check SL/TP
    await _manage_positions(client, boba)

    # Log the decision
    decision.reasoning_summary = (
        f"[{event.trigger.value}] Signals: {decision.signals_detected}, "
        f"Analyses: {decision.analyses_produced}, "
        f"Trades: {decision.trades_executed}"
    )
    save_decision(decision)

    _save_snapshot()


async def _process_signal(
    client: genai.Client, boba: BobaClient, signal: Signal
) -> Position | None:
    """Process a single signal through the full pipeline: analyze -> risk -> execute.

    Extracted from the ``run_cycle`` for-loop so it can be used by both the
    legacy scheduler path and the new event-driven path.
    """
    analysis = await _analyze_signal(client, boba, signal)
    if analysis is None:
        return None

    # KOL conviction boost
    kol_matches = check_kol_alignment(
        analysis.suggested_asset, analysis.suggested_direction, minutes=60
    )
    if kol_matches:
        original = analysis.conviction_score
        analysis.conviction_score = min(
            1.0, analysis.conviction_score + KOL_SIGNAL_BOOST
        )
        kol_names = ", ".join(k.kol_name for k in kol_matches[:3])
        analysis.reasoning += (
            f" [KOL BOOST +{KOL_SIGNAL_BOOST:.0%}: {kol_names} "
            f"also went {analysis.suggested_direction.value} on {analysis.suggested_asset}]"
        )
        logger.info(
            "KOL boost: %.2f -> %.2f (aligned with %s)",
            original, analysis.conviction_score, kol_names,
        )

    if analysis.conviction_score < CONVICTION_THRESHOLD:
        logger.info(
            "Low conviction (%.2f) for %s -- skipping",
            analysis.conviction_score, signal.market_question,
        )
        return None

    # Risk gate
    allowed, reason = can_open_position(analysis.suggested_size_usd, 3)
    if not allowed:
        logger.warning("Risk blocked: %s", reason)
        return None
    allowed, reason = can_open_position_for_asset(
        analysis.suggested_asset, analysis.suggested_direction
    )
    if not allowed:
        if reason.startswith("FLIP:"):
            # Close the existing opposite position, then open the new one
            old_id = int(reason.split(":")[1])
            old_positions = get_open_positions()
            old_p = next((p for p in old_positions if p.id == old_id), None)
            if old_p:
                # Get current price to calculate final PnL
                current_price = await _get_asset_price(boba, old_p.asset)
                if current_price > 0:
                    if old_p.direction == Direction.LONG:
                        old_pnl = (current_price - old_p.entry_price) / old_p.entry_price * old_p.size_usd * old_p.leverage
                    else:
                        old_pnl = (old_p.entry_price - current_price) / old_p.entry_price * old_p.size_usd * old_p.leverage
                    old_pnl = round(old_pnl, 2)
                else:
                    old_pnl = old_p.pnl
                update_position(old_id, status=PositionStatus.CLOSED, pnl=old_pnl, closed_at=datetime.utcnow())
                logger.info(
                    "FLIPPED #%d %s %s -> PnL $%+.2f (closing to open %s)",
                    old_id, old_p.direction.value, old_p.asset, old_pnl, analysis.suggested_direction.value,
                )
        else:
            logger.warning("Risk blocked: %s", reason)
            return None

    # Token audit before execution
    safe = await _audit_before_trade(boba, analysis.suggested_asset)
    if not safe:
        logger.warning("Token audit flagged %s as risky -- skipping", analysis.suggested_asset)
        return None

    # Size and execute
    final_size = calculate_position_size(
        analysis.conviction_score, analysis.suggested_size_usd
    )
    if final_size <= 0:
        logger.info("Position too small (dust) for %s — skipping", analysis.suggested_asset)
        return None
    position = await _execute_trade(client, boba, analysis, final_size)
    return position


async def _audit_before_trade(boba: BobaClient, asset: str) -> bool:
    """Call audit_token to check for scams before trading.

    Returns ``True`` if the asset looks safe (or if the audit is unavailable).
    """
    try:
        result = await boba.call_tool("audit_token", {"token": asset})
        data = json.loads(result) if isinstance(result, str) else result
        if isinstance(data, dict):
            # Check common risk indicators
            risk = str(data.get("risk", data.get("risk_level", ""))).lower()
            if risk in ("high", "critical", "scam"):
                logger.warning(
                    "Token audit: %s flagged as %s", asset, risk,
                )
                return False
            score = data.get("score", data.get("safety_score"))
            if score is not None and float(score) < 0.3:
                logger.warning(
                    "Token audit: %s safety score %.2f (below threshold)", asset, float(score),
                )
                return False
        return True
    except Exception:
        # If the audit tool is unavailable or errors, proceed (it's optional)
        return True
