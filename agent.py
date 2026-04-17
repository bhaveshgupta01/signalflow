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
    TRADABLE_ASSETS, ASSET_MAJORS,
    SCORE_THRESHOLD_MAJORS, SCORE_THRESHOLD_ALTS,
    HL_WHALE_TRIGGER_INTERVAL,
)
from db import (
    get_open_positions,
    get_performance_context,
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
    calculate_position_size_v2,
    can_open_position,
    can_open_position_for_asset,
    chandelier_stop,
    check_drawdown,
    check_orderbook_liquidity,
    check_trade_cooldown,
    check_trend_alignment,
    clamp_leverage,
    compute_atr,
    compute_stop_take,
    compute_stop_take_atr,
    confirm_fill_and_track_slippage,
)
from scoring import TradeScore, evaluate_trade
from db import save_signal_attribution, get_position_extra
from kol_tracker import check_kol_alignment, detect_kol_signals
from signals import detect_signals

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are SignalFlow, a systematic AI crypto trading agent managing a paper \
portfolio on Hyperliquid perpetual futures. You combine prediction market \
intelligence with on-chain data to find short-term edges.

## Analysis Framework (inspired by institutional quant desks)

When you receive a signal, execute this structured analysis:

### Step 1: Context Snapshot
- What is the current regime? (risk-on/risk-off, trending/ranging)
- What is the broader crypto market doing? (BTC dominance, total market trend)
- Are there upcoming macro catalysts? (Fed, CPI, major unlocks, expiries)

### Step 2: Signal Quality Assessment (Dog vs Tail)
- DOG (Spot/Structure): What does the 4h chart structure look like? Higher highs? \
  Support/resistance levels? EMA alignment?
- TAIL (Derivatives): What does Hyperliquid funding rate say? Is the trade crowded? \
  What does open interest and order book depth tell you?
- SENTIMENT: What does the Polymarket probability shift imply? Is the move backed \
  by holder concentration changes or just noise?

### Step 3: Hypothesis Generation
For each viable trade, define:
- THESIS: Clear 1-sentence directional view with specific catalyst
- EDGE TYPE: Flow (following smart money), Mean Reversion (fading extremes), \
  Narrative (catalyst-driven), or Sentiment (contrarian)
- EDGE DEPTH: Deep (structural, multi-factor) or Shallow (single signal, tactical)
- INVALIDATION: Specific price level or condition that kills the thesis
- TIMEFRAME: Scalp (30min-2h), Short Swing (2-12h), or Swing (12h-4d)

### Step 4: Decision
Return JSON (no markdown fences):
{
  "conviction": <float 0.0-1.0>,
  "direction": "long" | "short",
  "asset": "<BTC, ETH, SOL, DOGE, ARB, AVAX, LINK, etc>",
  "suggested_size_usd": 0,
  "leverage": <int 1-5, default 3 unless you have a strong reason>,
  "hold_hours": <float 0.5-6>,
  "reasoning": "<your thesis + edge type + what data supports it>",
  "risk_notes": "<invalidation condition + what could go wrong>",
  "edge_type": "<flow|mean_reversion|narrative|sentiment>",
  "edge_depth": "<deep|shallow>"
}

## Conviction Calibration
- 0.0-0.3: No clear edge, or conflicting signals. Skip.
- 0.3-0.5: Weak edge, single factor. Trade only if risk/reward > 2:1.
- 0.5-0.7: Moderate edge, 2+ factors align. Standard position size.
- 0.7-0.9: Strong edge, multiple factors converge. Full position.
- 0.9-1.0: Exceptional edge, rare. Max size with tight invalidation.

## Sizing (you do NOT pick the size — leave `suggested_size_usd` as 0)
The risk engine derives notional from the actual ATR-based stop distance using
fixed-fractional risk (1.5% of wallet per trade). Your job is direction and
conviction only. Whatever you put in `suggested_size_usd` is ignored.

## Key Rules
- Use the available tools aggressively to gather data before deciding.
- You MUST trade diverse assets — don't just default to BTC. Consider SOL, ETH, \
  DOGE, ARB, AVAX, LINK, OP, SUI, MATIC based on where the signal points.
- A Polymarket probability shift of 5%+ combined with aligned funding rate or \
  whale activity is a MODERATE edge (0.5+), not noise.
- When Polymarket AND whale activity align on direction, that's a STRONG edge (0.7+).
- Funding rate divergence >0.01% combined with price structure = tradeable edge.
- Do not default to low conviction just because you're uncertain about one factor. \
  Weight the factors: 2 out of 3 aligning is enough for 0.5+ conviction.
- Be willing to act. Inaction has a cost — missed opportunities compound.
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
                "Low conviction (%.2f < %.2f) for %s — skipping",
                analysis.conviction_score, CONVICTION_THRESHOLD,
                signal.market_question[:50],
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


# ── Learning Loop: Historical Performance Context ────────────────────────────

# Common crypto assets that might appear in Polymarket questions
_KNOWN_ASSETS = [
    "BTC", "ETH", "SOL", "DOGE", "ARB", "AVAX", "LINK", "OP", "SUI", "MATIC",
    "BNB", "XRP", "ADA", "LTC", "ATOM", "NEAR", "INJ", "TIA", "SEI", "APT",
]

_ASSET_KEYWORDS = {
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "eth", "ether"],
    "SOL": ["solana", "sol"],
    "DOGE": ["dogecoin", "doge"],
    "ARB": ["arbitrum", "arb"],
    "AVAX": ["avalanche", "avax"],
    "LINK": ["chainlink", "link"],
    "OP": ["optimism", "op"],
    "MATIC": ["polygon", "matic"],
    "XRP": ["ripple", "xrp"],
}


def _detect_likely_assets(question: str, category: str) -> list[str]:
    """Extract likely asset symbols from a Polymarket question/category."""
    text = (question + " " + category).lower()
    found: list[str] = []
    for asset, keywords in _ASSET_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            found.append(asset)
    return found or ["BTC"]   # default to BTC if nothing detected


def _format_perf(perf: dict, label: str) -> str:
    """Format a performance bucket as a one-line summary."""
    s = perf
    if s["trades"] == 0:
        return f"  • {label}: no history"
    return (
        f"  • {label}: {s['trades']} trades, "
        f"{s['win_rate']:.0f}% win rate, "
        f"total ${s['total_pnl']:+.2f}, "
        f"avg ${s['avg_pnl']:+.3f}/trade"
    )


def _build_learning_context(question: str, category: str) -> str:
    """Build the historical-performance section injected into the analysis prompt."""
    assets = _detect_likely_assets(question, category)
    primary = assets[0]

    lines = ["\n## Your Recent Performance (last 7 days) — LEARN FROM THIS"]

    # Long perf for primary asset
    long_perf = get_performance_context(primary, "long", days=7)
    lines.append(f"\n{primary} LONG:")
    lines.append(_format_perf(long_perf["exact_match"], "exact pattern"))

    # Short perf for primary asset
    short_perf = get_performance_context(primary, "short", days=7)
    lines.append(f"\n{primary} SHORT:")
    lines.append(_format_perf(short_perf["exact_match"], "exact pattern"))

    # Overall + same-direction context (use long_perf since they share overall stats)
    lines.append("")
    lines.append(_format_perf(long_perf["overall"], "ALL trades 7d"))

    # Recent similar trades with reasoning — most useful learning signal
    recent = long_perf["recent_similar"][:2] + short_perf["recent_similar"][:2]
    if recent:
        lines.append(f"\nLast few {primary} trades (with reasoning):")
        for r in recent[:3]:
            outcome = "WIN" if r["pnl"] > 0 else "LOSS"
            lines.append(
                f"  • {outcome} ${r['pnl']:+.2f} (conv {r['conviction']:.2f}): "
                f"{r['reasoning'][:120]}"
            )

    return "\n".join(lines)


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

    # Help Gemini interpret the signal correctly — with strict guardrails
    # CRITICAL FIX: "won't reach target" ≠ "will go down"
    # A drop in "Will SOL reach $110?" from 10% to 5% means the $110 target is unlikely.
    # It says NOTHING about whether SOL will drop from $82. It could rally to $100 and
    # the $110 probability would still be low.
    interpretation_hint = ""
    q = signal.market_question.lower()
    if "dip" in q or "drop" in q or "fall" in q or "below" in q:
        if signal.price_change_pct < 0:
            interpretation_hint = (
                "IMPORTANT: This is a 'dip/drop' market and its probability FELL. "
                "That means the market thinks a dip is LESS likely now = BULLISH for the asset. "
                "This is a genuine bullish signal — consider going LONG."
            )
        else:
            interpretation_hint = (
                "IMPORTANT: This is a 'dip/drop' market and its probability ROSE. "
                "That means the market thinks a dip is MORE likely = BEARISH for the asset. "
                "This is a genuine bearish signal — consider going SHORT."
            )
    elif "above" in q or "reach" in q or "rise" in q or "hit" in q:
        if signal.price_change_pct > 0:
            interpretation_hint = (
                "IMPORTANT: This is a 'reach/above' market and its probability ROSE. "
                "That means the market is MORE bullish = BULLISH for the asset. "
                "This is a genuine bullish signal — consider going LONG."
            )
        else:
            interpretation_hint = (
                "NOTE: This is a 'reach/above' market and its probability FELL. "
                "This means the specific target price is now seen as less likely. "
                "It does NOT necessarily mean the asset will decline — the target may "
                "just be too ambitious. Use Hyperliquid price data and funding rates "
                "to determine actual directional bias. If the asset's spot price is "
                "also declining or funding is negative, this reinforces a bearish view. "
                "If spot is stable/rising, the signal may be weak — adjust conviction accordingly."
            )

    # ── LEARNING LOOP: inject historical performance for the likely asset ──
    # Detect mentioned assets in the signal so we can show how past similar trades did
    learning_context = _build_learning_context(signal.market_question, signal.category)

    user_msg = (
        f"Analyze this prediction market signal:\n"
        f"- Market: {signal.market_question}\n"
        f"- Price moved {signal.price_change_pct:+.1%} in {signal.timeframe_minutes} minutes\n"
        f"- Current price/probability: {signal.current_price:.3f}\n"
        f"- Category: {signal.category}\n"
        f"{interpretation_hint}\n"
        f"{sentiment_context}\n"
        f"{learning_context}\n\n"
        f"Use the tools to gather Hyperliquid and Polymarket data, then return your JSON analysis. "
        f"IMPORTANT: Factor in the historical performance above. If past similar trades have lost money, "
        f"either (a) lower conviction, (b) flip direction, or (c) skip. If past trades have won, "
        f"increase conviction and size up. Learn from the pattern."
    )

    try:
        result_text = await _run_tool_loop(client, boba, SYSTEM_PROMPT, user_msg)
        parsed = _extract_json(result_text)
        if parsed is None:
            logger.warning("Could not parse analysis JSON from Gemini response")
            return None

        conviction = float(parsed.get("conviction", 0))
        leverage = clamp_leverage(int(parsed.get("leverage", 3)), conviction)
        hold_hours = max(0.5, min(6.0, float(parsed.get("hold_hours", 2.0))))
        analysis = Analysis(
            signal_id=signal.id or 0,
            reasoning=parsed.get("reasoning", ""),
            conviction_score=conviction,
            suggested_direction=Direction(parsed.get("direction", "long")),
            suggested_asset=parsed.get("asset", "BTC"),
            suggested_size_usd=float(parsed.get("suggested_size_usd", 100)),
            risk_notes=f"leverage={leverage} hold={hold_hours}h " + parsed.get("risk_notes", ""),
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
    score: TradeScore | None = None,
) -> Position | None:
    """Open a perps position with v2 execution pipeline.

    v2 changes:
      - Asset whitelist enforced (rejects garbage `suggested_asset`)
      - ATR computed once and reused for SL, TP, and chandelier
      - Position size derived from ACTUAL stop distance (fixed-fractional)
      - extreme_price + atr_at_entry persisted for chandelier trailing
    """
    # ── v2: Asset whitelist gate ──
    asset_u = (analysis.suggested_asset or "").upper()
    if asset_u not in TRADABLE_ASSETS:
        logger.warning(
            "Whitelist rejected '%s' (not in TRADABLE_ASSETS) — skipping",
            analysis.suggested_asset,
        )
        return None
    # Normalize the analysis asset for downstream calls
    analysis.suggested_asset = asset_u

    # Extract leverage from risk_notes
    leverage = 3
    if analysis.risk_notes and "leverage=" in analysis.risk_notes:
        try:
            leverage = int(analysis.risk_notes.split("leverage=")[1].split()[0].strip(","))
        except (ValueError, IndexError):
            pass
    leverage = clamp_leverage(leverage, analysis.conviction_score)

    # Get entry price
    entry_price = await _get_asset_price(boba, analysis.suggested_asset)
    if entry_price <= 0:
        logger.warning("Could not fetch entry price for %s", analysis.suggested_asset)
        return None

    # ── v2: Compute ATR once, reuse for SL/TP/chandelier ──
    atr = await compute_atr(boba, analysis.suggested_asset)

    # ── ATR-based dynamic stops (no caps in v2) ──
    stop_loss, take_profit = await compute_stop_take_atr(
        boba, entry_price, analysis.suggested_direction, analysis.suggested_asset
    )

    # ── v2: Re-derive size from the ACTUAL stop distance (fixed-fractional risk) ──
    stop_distance_pct = abs(entry_price - stop_loss) / entry_price if entry_price > 0 else 0.025
    size_usd = calculate_position_size_v2(stop_distance_pct=stop_distance_pct, leverage=leverage)
    if size_usd <= 0:
        logger.info("v2 sizing returned 0 for %s — skipping", analysis.suggested_asset)
        return None

    # ── Orderbook liquidity check (after final size known) ──
    is_liquid, est_slippage, liq_reason = await check_orderbook_liquidity(
        boba, analysis.suggested_asset, size_usd, analysis.suggested_direction
    )
    if not is_liquid:
        logger.warning("Orderbook rejected %s: %s", analysis.suggested_asset, liq_reason)
        return None

    # ── Direct execution via Boba (v2: no LLM fallback) ──
    # The fallback was masking real execution failures AND skipping v2
    # telemetry (extreme_price, atr_at_entry, signal_attribution). If any
    # critical step fails here we log loudly and return None so we see it.
    side = "buy" if analysis.suggested_direction == Direction.LONG else "sell"

    # Leverage & market order are the only steps whose failure MUST abort.
    try:
        await boba.call_tool("hl_update_leverage", {
            "coin": analysis.suggested_asset,
            "leverage": leverage,
            "mode": "cross",
        })
    except Exception:
        logger.exception("hl_update_leverage failed for %s — aborting trade", analysis.suggested_asset)
        return None

    try:
        order_result = await boba.call_tool("hl_place_order", {
            "coin": analysis.suggested_asset,
            "side": side,
            "size": size_usd,
            "type": "market",
        })
        logger.info("hl_place_order (entry) result: %s", str(order_result)[:200])
    except Exception:
        logger.exception("Market order failed for %s — aborting trade", analysis.suggested_asset)
        return None

    # Confirm fill (best-effort — don't abort on failure)
    actual_price, slippage = await confirm_fill_and_track_slippage(
        boba, analysis.suggested_asset, entry_price, analysis.suggested_direction
    )
    if actual_price and actual_price > 0:
        entry_price = actual_price
        new_stops = await compute_stop_take_atr(
            boba, actual_price, analysis.suggested_direction, analysis.suggested_asset
        )
        stop_loss, take_profit = new_stops

    # SL/TP placements are best-effort; mechanical SL/TP is also enforced
    # in _manage_positions so the position stays safe even if these fail.
    sl_side = "sell" if analysis.suggested_direction == Direction.LONG else "buy"
    for label, order_type, trigger in (
        ("SL", "stop", stop_loss),
        ("TP", "take_profit", take_profit),
    ):
        try:
            await boba.call_tool("hl_place_order", {
                "coin": analysis.suggested_asset,
                "side": sl_side,
                "size": size_usd,
                "type": order_type,
                "triggerPrice": str(trigger),
            })
        except Exception as e:
            logger.warning(
                "%s order placement failed for %s (%s) — proceeding; mechanical check will still close.",
                label, analysis.suggested_asset, e,
            )

    slippage_note = f" slippage={slippage:+.3%}" if slippage is not None else ""
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

    # v2: seed chandelier extreme tracker and store ATR for trailing logic
    from db import update_position as _upd
    _upd(
        position.id,
        extreme_price=entry_price,
        atr_at_entry=atr if atr else None,
    )

    # v2: persist signal attribution if scoring was used
    if score is not None:
        try:
            save_signal_attribution(
                position.id,
                score_funding=score.score_funding,
                score_polymarket=score.score_polymarket,
                score_kol=score.score_kol,
                score_trend=score.score_trend,
                score_total=score.total,
                direction=score.direction.value,
                notes=" | ".join(score.notes)[:500],
            )
        except Exception:
            logger.debug("Failed to save signal attribution", exc_info=True)

    logger.info(
        "Opened %s %s $%.0f @ %.4f (SL: %.2f, TP: %.2f%s) atr=%s score=%s",
        position.direction.value, position.asset,
        position.size_usd, position.entry_price,
        position.stop_loss, position.take_profit, slippage_note,
        f"{atr:.4f}" if atr else "n/a",
        f"{score.total:+.2f}" if score else "n/a",
    )
    return position


# ── Phase 5: Position Management ─────────────────────────────────────────────

async def _manage_positions(
    client: genai.Client,
    boba: BobaClient,
) -> None:
    """v2 position management — purely mechanical.

    Pipeline per open position:
      1. Mark-to-market PnL + snapshot
      2. Hard SL hit → STOPPED
      3. Hard TP hit → CLOSED
      4. Update extreme_price (high since entry for longs / low for shorts)
      5. Chandelier trailing stop (only ratchets toward profit)
      6. Hard 12h max age → close (no AI consultation)

    No more AI exit calls. Winners ride to TP or chandelier; losers cut at SL.
    """
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

        # ── Hard stop-loss ──
        hit_sl = (p.direction == Direction.LONG and current_price <= p.stop_loss) or \
                 (p.direction == Direction.SHORT and current_price >= p.stop_loss)
        if hit_sl:
            await _close_position_on_exchange(boba, p.asset)
            update_position(p.id, status=PositionStatus.STOPPED, pnl=pnl, closed_at=now)
            logger.info("STOP #%d %s @ $%.2f -> PnL $%+.2f", p.id, p.asset, current_price, pnl)
            continue

        # ── Hard take-profit ──
        hit_tp = (p.direction == Direction.LONG and current_price >= p.take_profit) or \
                 (p.direction == Direction.SHORT and current_price <= p.take_profit)
        if hit_tp:
            await _close_position_on_exchange(boba, p.asset)
            update_position(p.id, status=PositionStatus.CLOSED, pnl=pnl, closed_at=now)
            logger.info("TP #%d %s @ $%.2f -> PnL $%+.2f", p.id, p.asset, current_price, pnl)
            continue

        # ── v2: Chandelier trailing stop ──
        extra = get_position_extra(p.id)
        prev_extreme = extra.get("extreme_price") or p.entry_price
        atr = extra.get("atr_at_entry")

        # Update extreme price for longs (highest high) / shorts (lowest low)
        if p.direction == Direction.LONG:
            new_extreme = max(prev_extreme, current_price)
        else:
            new_extreme = min(prev_extreme, current_price)
        if new_extreme != prev_extreme:
            update_position(p.id, extreme_price=new_extreme)

        if atr and atr > 0:
            new_sl, moved = chandelier_stop(
                direction=p.direction,
                entry_price=p.entry_price,
                extreme_price=new_extreme,
                atr=atr,
                current_stop=p.stop_loss,
            )
            if moved:
                update_position(p.id, stop_loss=new_sl)
                logger.info(
                    "CHANDELIER #%d %s SL %.4f -> %.4f (extreme=%.4f, atr=%.4f)",
                    p.id, p.asset, p.stop_loss, new_sl, new_extreme, atr,
                )

        # ── Hard 12h max age (mechanical, no AI consult) ──
        if age_hours >= MAX_POSITION_AGE_HOURS:
            await _close_position_on_exchange(boba, p.asset)
            status = PositionStatus.CLOSED if pnl >= 0 else PositionStatus.STOPPED
            update_position(p.id, status=status, pnl=pnl, closed_at=now)
            logger.info(
                "MAX-AGE #%d %s after %.1fh -> PnL $%+.2f",
                p.id, p.asset, age_hours, pnl,
            )


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


async def _close_position_on_exchange(boba: BobaClient, asset: str) -> bool:
    """Close a position on Hyperliquid using hl_close_position (atomic, no dust)."""
    try:
        result = await boba.call_tool("hl_close_position", {"coin": asset})
        logger.info("hl_close_position %s: %s", asset, str(result)[:200])
        return True
    except Exception:
        logger.debug("hl_close_position failed for %s — position may already be closed", asset, exc_info=True)
        return False


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
        hl_rate = event.data.get("hl_rate", 0)
        logger.info("Funding spike: %s HL=%.4f%% (extreme=%s)",
                    asset, hl_rate * 100, event.data.get("extreme", False))

        # v2: route through the multi-source scoring layer
        score = None
        try:
            score = await asyncio.wait_for(
                evaluate_trade(boba, asset, hl_funding_rate=hl_rate), timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.warning("evaluate_trade timed out for funding %s — skipping", asset)
        if score is None:
            pass  # timeout or error — skip this funding event
        else:
            logger.info("SCORE %s", score.explain())
            decision.signals_detected = 1
            decision.analyses_produced = 1

            if score.passes():
                allowed, reason = can_open_position(50, 3)
                if not allowed:
                    logger.warning("Funding score passed but risk blocked: %s", reason)
                else:
                    allowed_asset, reason = can_open_position_for_asset(asset, score.direction)
                    if not allowed_asset and not reason.startswith("FLIP:"):
                        logger.info("Funding score passed but asset blocked: %s", reason)
                    else:
                        synthetic_signal = Signal(
                            market_id=f"funding_{asset}_{cycle_id}",
                            market_question=f"Funding extreme: {asset} HL {hl_rate*100:+.4f}%",
                            current_price=0.5,
                            price_change_pct=hl_rate,
                            timeframe_minutes=120,
                            category="funding",
                        )
                        synthetic_signal = save_signal(synthetic_signal)
                        analysis = Analysis(
                            signal_id=synthetic_signal.id or 0,
                            reasoning=f"v2 multi-source: {score.explain()}",
                            conviction_score=min(1.0, score.confidence / 3.0),
                            suggested_direction=score.direction,
                            suggested_asset=asset,
                            suggested_size_usd=0.0,
                            risk_notes=f"leverage=3 hold=4 v2_score={score.total:+.2f}",
                        )
                        analysis = save_analysis(analysis)
                        position = await _execute_trade(client, boba, analysis, 0.0, score=score)
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

    elif event.trigger == TriggerType.HL_WHALE_FLOW:
        # v2.2: aggregated Hyperliquid perp whale imbalance
        asset = event.data["asset"]
        direction = Direction(event.data["direction"])
        ratio = event.data.get("ratio", 0)
        buy_usd = event.data.get("buy_usd", 0)
        sell_usd = event.data.get("sell_usd", 0)
        logger.info(
            "HL whale event: %s %s ratio=%.2fx ($%.0fk buy / $%.0fk sell)",
            asset, direction.value, ratio, buy_usd / 1000, sell_usd / 1000,
        )
        decision.signals_detected = 1
        decision.analyses_produced = 1

        # Fetch funding to enrich the score
        hl_rate: float | None = None
        try:
            raw = await boba.call_tool("hl_get_predicted_funding", {})
            data = json.loads(raw) if isinstance(raw, str) else raw
            rates = data if isinstance(data, list) else data.get("rates", data.get("assets", []))
            for r in rates:
                r_asset = (r.get("name") or r.get("asset") or r.get("coin") or "").upper()
                if r_asset == asset:
                    hl_rate = float(r.get("hl", r.get("funding", 0)) or 0)
                    break
        except Exception:
            pass

        # Always save to signals table so the dashboard shows what the agent sees
        interp = event.data.get("interpretation", "")
        oi_change = event.data.get("oi_change", 0)
        synthetic_signal = Signal(
            market_id=f"hl_whale_{asset}_{cycle_id}",
            market_question=f"HL OI {oi_change*100:+.1f}% on {asset} ({interp})",
            current_price=event.data.get("mark", 0),
            price_change_pct=oi_change,
            timeframe_minutes=HL_WHALE_TRIGGER_INTERVAL // 60,
            category="hl_whale",
        )
        synthetic_signal = save_signal(synthetic_signal)

        score = None
        try:
            score = await asyncio.wait_for(
                evaluate_trade(boba, asset, hl_funding_rate=hl_rate), timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.warning("evaluate_trade timed out for HL whale %s — skipping", asset)
        if score is None:
            pass  # timeout — skip this HL whale event
        else:
            whale_intensity = min(1.0, (ratio - 1.0) / 3.0)
            whale_sign = 1.0 if direction == Direction.LONG else -1.0
            from config import SCORE_WEIGHT_KOL
            score.score_kol = whale_sign * whale_intensity * SCORE_WEIGHT_KOL
            score.notes.append(f"HL whale ratio={ratio:.2f}x → {score.score_kol:+.2f}")
            logger.info("SCORE (HL whale) %s", score.explain())

            if score.passes():
                allowed, reason = can_open_position(50, 3)
                if not allowed:
                    logger.warning("HL whale score passed but risk blocked: %s", reason)
                else:
                    allowed_asset, reason = can_open_position_for_asset(asset, score.direction)
                    if not allowed_asset and not reason.startswith("FLIP:"):
                        logger.info("HL whale blocked on asset: %s", reason)
                    else:
                        analysis = Analysis(
                            signal_id=synthetic_signal.id or 0,
                            reasoning=f"v2.2 HL whale flow: {score.explain()}",
                            conviction_score=min(1.0, score.confidence / 3.0),
                            suggested_direction=score.direction,
                            suggested_asset=asset,
                            suggested_size_usd=0.0,
                            risk_notes=f"leverage=3 hold=4 v2_score={score.total:+.2f} hl_whale={ratio:.2f}x",
                        )
                        analysis = save_analysis(analysis)
                        position = await _execute_trade(client, boba, analysis, 0.0, score=score)
                        if position:
                            decision.trades_executed = 1
                            trade_opened = True

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
    """Process a Polymarket signal through analyze -> v2 score -> risk -> execute."""
    analysis = await _analyze_signal(client, boba, signal)
    if analysis is None:
        return None

    # ── v2: whitelist gate before any further work ──
    asset_u = (analysis.suggested_asset or "").upper()
    if asset_u not in TRADABLE_ASSETS:
        logger.info(
            "Whitelist rejected '%s' from PM signal — skipping",
            analysis.suggested_asset,
        )
        return None
    analysis.suggested_asset = asset_u

    # ── v2: multi-source scoring (funding + PM + KOL + trend) ──
    # Try to fetch current funding rate for this asset to enrich the score.
    hl_rate: float | None = None
    try:
        import json as _json
        raw = await boba.call_tool("hl_get_predicted_funding", {})
        data = _json.loads(raw) if isinstance(raw, str) else raw
        rates = data if isinstance(data, list) else data.get("rates", data.get("assets", []))
        for r in rates:
            r_asset = (r.get("name") or r.get("asset") or r.get("coin") or "").upper()
            if r_asset == asset_u:
                hl_rate = float(r.get("hl", r.get("funding", 0)) or 0)
                break
    except Exception:
        logger.debug("Couldn't fetch funding for %s in score", asset_u)

    # v2.1 had a BTC/ETH PM gate here that required extreme funding before
    # allowing any PM signal on majors. Removed in v2.2.2: overnight audit
    # showed it killed a legitimate 0.70-conviction ETH short backed by a
    # -43.7% PM move. The scoring system's SCORE_THRESHOLD_MAJORS (1.1) already
    # provides a higher bar for BTC/ETH vs alts (0.65). Double-filtering was
    # too aggressive — the agent went 8 hours without trading despite real setups.

    try:
        score = await asyncio.wait_for(
            evaluate_trade(
                boba,
                asset_u,
                hl_funding_rate=hl_rate,
                pm_price_change=signal.price_change_pct,
                pm_direction_hint=analysis.suggested_direction,
            ),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        logger.warning("evaluate_trade timed out for PM signal %s — skipping", asset_u)
        return None
    logger.info("SCORE %s", score.explain())

    if not score.passes():
        logger.info(
            "v2 score %.2f below threshold %.2f for %s — skipping",
            score.confidence, score.threshold(), asset_u,
        )
        return None

    # Score wins → use score's direction (may flip the LLM's call if funding/KOL/trend overwhelm)
    if score.direction != analysis.suggested_direction:
        logger.info(
            "v2 score flipped direction: %s -> %s",
            analysis.suggested_direction.value, score.direction.value,
        )
        analysis.suggested_direction = score.direction

    # Legacy KOL boost is now redundant (score includes KOL) — skip.

    if analysis.conviction_score < CONVICTION_THRESHOLD:
        # v2: use score confidence as fallback if LLM under-rated
        analysis.conviction_score = max(
            analysis.conviction_score, min(1.0, score.confidence / 3.0)
        )

    # ── v2.1: deterministic learning cap from recent same-asset/direction PnL ──
    # Rule: if the last 10 trades of this exact pattern lost net money, cap
    # conviction at 0.30 (discourages doubling down on a losing pattern).
    # If they won >= +$1, give a +0.10 boost (reinforces what's working).
    try:
        perf = get_performance_context(
            analysis.suggested_asset,
            analysis.suggested_direction.value,
            days=7,
        )
        exact = perf.get("exact_match", {})
        n, total_pnl = exact.get("trades", 0), exact.get("total_pnl", 0.0)
        if n >= 5:  # need enough sample
            if total_pnl <= -0.5:
                cap_before = analysis.conviction_score
                analysis.conviction_score = min(analysis.conviction_score, 0.30)
                logger.info(
                    "LEARN-CAP %s %s: recent %d trades netted $%+.2f — capped conv %.2f→%.2f",
                    analysis.suggested_asset, analysis.suggested_direction.value,
                    n, total_pnl, cap_before, analysis.conviction_score,
                )
            elif total_pnl >= 1.0:
                boost_before = analysis.conviction_score
                analysis.conviction_score = min(1.0, analysis.conviction_score + 0.10)
                logger.info(
                    "LEARN-BOOST %s %s: recent %d trades netted $%+.2f — boosted conv %.2f→%.2f",
                    analysis.suggested_asset, analysis.suggested_direction.value,
                    n, total_pnl, boost_before, analysis.conviction_score,
                )
    except Exception:
        logger.debug("Learning-cap lookup failed", exc_info=True)

    # Anti-churn: cooldown between trades on same asset
    allowed, reason = check_trade_cooldown(analysis.suggested_asset)
    if not allowed:
        logger.info("Cooldown blocked: %s", reason)
        return None

    # Trend regime check: block counter-trend trades
    allowed, reason = await check_trend_alignment(
        boba, analysis.suggested_asset, analysis.suggested_direction
    )
    if not allowed:
        logger.warning("Trend blocked: %s", reason)
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
                # Close on exchange first, then update DB
                await _close_position_on_exchange(boba, old_p.asset)
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

    # v2: _execute_trade re-derives size from the actual stop distance, so we
    # pass 0 here. score carries the per-source attribution to be persisted.
    position = await _execute_trade(client, boba, analysis, 0.0, score=score)
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
