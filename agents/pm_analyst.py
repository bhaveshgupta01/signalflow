"""PM Analyst — Polymarket prediction market specialist.

Triggered by POLYMARKET_MOVE events. Interprets probability shifts,
enriches with holder/comment data, and produces TradeProposals.

Does NOT see: wallet balance, open positions, other agents' proposals.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from agents.base import BaseSpecialist
from config import SPECIALIST_MODEL, TRADABLE_ASSETS
from db import get_performance_context, save_proposal
from models import Direction, TradeProposal

logger = logging.getLogger(__name__)

# Asset detection keywords for mapping PM questions to tradable assets
_ASSET_KEYWORDS = {
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "eth", "ether"],
    "SOL": ["solana", "sol"],
    "DOGE": ["dogecoin", "doge"],
    "ARB": ["arbitrum", "arb"],
    "AVAX": ["avalanche", "avax"],
    "LINK": ["chainlink", "link"],
    "OP": ["optimism", "op"],
    "SUI": ["sui"],
    "INJ": ["injective", "inj"],
    "APT": ["aptos", "apt"],
    "MATIC": ["polygon", "matic"],
    "XRP": ["ripple", "xrp"],
}


class PMAnalyst(BaseSpecialist):
    AGENT_ID = "pm_analyst"
    MODEL = SPECIALIST_MODEL

    SYSTEM_PROMPT = """\
You are the Polymarket Analyst for SignalFlow, a multi-agent crypto trading system.
Your ONLY job: interpret prediction market probability shifts and decide if they
imply a tradeable edge on Hyperliquid perpetual futures.

## Your Expertise
- Expert in interpreting prediction market probability shifts
- Understanding dip/reach/above/below semantics in market questions
- Distinguishing noise (SEC, USDC, generic "crypto" markets) from signal
  (asset-specific price targets with real probability movement)
- Cross-referencing PM data with Hyperliquid funding rates for confirmation

## Signal Interpretation Rules
- "dip/drop/fall/below" market + probability FELL = market thinks dip LESS likely = BULLISH
- "dip/drop/fall/below" market + probability ROSE = market thinks dip MORE likely = BEARISH
- "above/reach/rise/hit" market + probability ROSE = MORE bullish = LONG signal
- "above/reach/rise/hit" market + probability FELL = target less likely, but does NOT
  necessarily mean the asset will decline. Check HL data for actual direction.

## MANDATORY: Multi-Factor Confirmation
You MUST gather at least 2 of these 3 data sources BEFORE deciding:
1. hl_get_predicted_funding — does funding confirm direction? (contrarian: positive = crowd long)
2. pm_get_top_holders — are whales positioning? (>5 large holders = real signal)
3. hl_get_markets — check 24h volume and OI for the asset

If you only have the PM move and NOTHING else confirms it, cap conviction at 0.40.
Single-factor sentiment trades lose money. You need CONFIRMATION.

## Output Format
CRITICAL: Your final response MUST be a single JSON object with NO markdown fences,
NO explanatory text before or after. Just the raw JSON. Example:
{"asset":"ETH","direction":"long","conviction":0.65,"edge_type":"sentiment","reasoning":"...","suggested_risk_pct":0.015,"timeframe_hours":4,"invalidation":"ETH below $2300"}

Required fields:
- "asset": one of BTC|ETH|SOL|DOGE|ARB|AVAX|LINK|SUI|INJ|OP|APT
- "direction": "long" or "short"
- "conviction": float 0.0-1.0
- "edge_type": "sentiment"
- "reasoning": your thesis + what data supports it + what confirmed it
- "suggested_risk_pct": float 0.005-0.03
- "timeframe_hours": float 1-12
- "invalidation": specific price level or condition

## Conviction Calibration (STRICT — sentiment alone is NOT enough)
- 0.0-0.3: No edge, conflicting signals, or PM-only with no confirmation. SKIP.
- 0.3-0.5: PM move exists but only 1 confirming factor. Low conviction.
- 0.5-0.7: PM move 5%+ with funding OR holder confirmation. Standard.
- 0.7-0.9: PM move 10%+ with BOTH funding AND holder confirmation. Strong.
- 0.9-1.0: Massive PM shift + funding extreme + whale positioning. Exceptional.

IMPORTANT: If past trades on this asset+direction have been LOSING money
(shown in performance data), REDUCE conviction by 0.15 or flip direction.

## Key Rules
- You do NOT decide position size (the orchestrator does that).
- You do NOT see wallet balance or open positions.
- ALWAYS use tools to gather data before responding — never analyze from PM data alone.
- Your FINAL message must be ONLY the JSON object, nothing else.
"""

    async def handle(self, event_data: dict[str, Any]) -> list[dict]:
        """Process a POLYMARKET_MOVE event and return proposal dicts."""
        signal = event_data.get("signal")
        if signal is None:
            return []

        question = signal.market_question
        price_change = signal.price_change_pct
        current_price = signal.current_price
        category = signal.category
        market_id = signal.market_id

        # Detect likely asset from the question
        asset = self._detect_asset(question, category)
        if asset not in TRADABLE_ASSETS:
            logger.info("[%s] No tradable asset found in '%s'", self.AGENT_ID, question[:60])
            return []

        # Build interpretation hint
        interpretation = self._build_interpretation_hint(question, price_change)

        # Build learning context from historical performance
        learning = self._build_learning_context(asset)

        # Enrich with PM data before sending to Gemini
        enrichment = await self._enrich_pm_data(market_id)

        # Pre-fetch funding rate so we can validate multi-factor confirmation
        funding_context = ""
        funding_confirmed = False
        try:
            raw = await self.boba.call_tool("hl_get_predicted_funding", {})
            data = json.loads(raw) if isinstance(raw, str) else raw
            rates = data if isinstance(data, list) else data.get("rates", data.get("assets", []))
            for r in rates:
                r_asset = (r.get("name") or r.get("asset") or r.get("coin") or "").upper()
                if r_asset == asset:
                    hl_rate = float(r.get("hl", r.get("funding", 0)) or 0)
                    funding_context = f"\nHL funding rate for {asset}: {hl_rate*100:+.4f}%"
                    # Funding confirms direction if rate is extreme
                    if abs(hl_rate) > 0.0002:
                        funding_confirmed = True
                    break
        except Exception:
            pass

        user_msg = (
            f"Analyze this Polymarket signal:\n"
            f"- Market: {question}\n"
            f"- Price moved {price_change:+.1%} recently\n"
            f"- Current probability: {current_price:.3f}\n"
            f"- Category: {category}\n\n"
            f"{interpretation}\n"
            f"{enrichment}\n"
            f"{funding_context}\n"
            f"{learning}\n\n"
            f"Use tools to gather MORE data (holders, orderbook, candles), "
            f"then return ONLY the JSON object — no other text."
        )

        try:
            result_text = await self.run_tool_loop(user_msg)
            parsed = self.extract_json(result_text)
            if parsed is None:
                logger.warning("[%s] Could not parse JSON from response", self.AGENT_ID)
                return []

            conviction = float(parsed.get("conviction", 0))
            reasoning = parsed.get("reasoning", "")

            # ── Multi-factor gate: PM-only signals get capped ──
            has_holder_data = "holder" in reasoning.lower() or "whale" in reasoning.lower()
            has_funding_data = "funding" in reasoning.lower() or funding_confirmed
            confirming_factors = sum([has_holder_data, has_funding_data])

            if confirming_factors == 0:
                # PM-only, no confirmation — hard cap at 0.40
                if conviction > 0.40:
                    logger.info(
                        "[%s] Capping conviction %.2f -> 0.40 (PM-only, no multi-factor confirmation)",
                        self.AGENT_ID, conviction,
                    )
                    conviction = 0.40

            # ── Learning penalty: if past trades on this pattern lost money, reduce ──
            perf = get_performance_context(
                (parsed.get("asset", asset) or asset).upper(),
                parsed.get("direction", "long"),
                days=7,
            )
            exact = perf.get("exact_match", {})
            if exact.get("trades", 0) >= 2 and exact.get("total_pnl", 0) < -0.5:
                old_conv = conviction
                conviction = max(0.0, conviction - 0.15)
                logger.info(
                    "[%s] Learning penalty: %d trades lost $%.2f on %s %s — conv %.2f -> %.2f",
                    self.AGENT_ID, exact["trades"], exact["total_pnl"],
                    parsed.get("asset", asset), parsed.get("direction", "long"),
                    old_conv, conviction,
                )

            # ── Minimum conviction floor: don't waste orchestrator time ──
            if conviction < 0.35:
                logger.info(
                    "[%s] Conviction %.2f below floor 0.35 — skipping proposal",
                    self.AGENT_ID, conviction,
                )
                return []

            proposal = TradeProposal(
                agent_id=self.AGENT_ID,
                asset=(parsed.get("asset", asset) or asset).upper(),
                direction=Direction(parsed.get("direction", "long")),
                conviction=conviction,
                edge_type=parsed.get("edge_type", "sentiment"),
                reasoning=reasoning,
                suggested_risk_pct=float(parsed.get("suggested_risk_pct", 0.015)),
                timeframe_hours=float(parsed.get("timeframe_hours", 4.0)),
                invalidation=parsed.get("invalidation", ""),
            )

            if proposal.asset not in TRADABLE_ASSETS:
                proposal.asset = asset

            proposal = save_proposal(proposal)
            logger.info(
                "[%s] Proposal #%d: %s %s conv=%.2f edge=%s (factors=%d)",
                self.AGENT_ID, proposal.id, proposal.direction.value,
                proposal.asset, proposal.conviction, proposal.edge_type,
                confirming_factors,
            )
            return [proposal.model_dump()]

        except Exception:
            logger.exception("[%s] Failed to process PM signal", self.AGENT_ID)
            return []

    def _detect_asset(self, question: str, category: str) -> str:
        text = (question + " " + category).lower()
        for asset, keywords in _ASSET_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return asset
        return "BTC"

    def _build_interpretation_hint(self, question: str, price_change: float) -> str:
        q = question.lower()
        if "dip" in q or "drop" in q or "fall" in q or "below" in q:
            if price_change < 0:
                return (
                    "INTERPRETATION: 'dip/drop' market probability FELL → "
                    "market thinks dip is LESS likely = BULLISH for asset."
                )
            return (
                "INTERPRETATION: 'dip/drop' market probability ROSE → "
                "market thinks dip is MORE likely = BEARISH for asset."
            )
        if "above" in q or "reach" in q or "rise" in q or "hit" in q:
            if price_change > 0:
                return (
                    "INTERPRETATION: 'reach/above' market probability ROSE → "
                    "MORE bullish = consider LONG."
                )
            return (
                "NOTE: 'reach/above' market probability FELL. Target less likely, "
                "but does NOT necessarily mean asset will decline. Cross-check HL data."
            )
        return ""

    def _build_learning_context(self, asset: str) -> str:
        lines = ["\n## Recent Performance (learn from this)"]
        for direction in ("long", "short"):
            perf = get_performance_context(asset, direction, days=7)
            exact = perf.get("exact_match", {})
            if exact.get("trades", 0) > 0:
                lines.append(
                    f"  {asset} {direction.upper()}: {exact['trades']} trades, "
                    f"{exact['win_rate']:.0f}% win, total ${exact['total_pnl']:+.2f}"
                )
            recent = perf.get("recent_similar", [])
            for r in recent[:2]:
                outcome = "WIN" if r["pnl"] > 0 else "LOSS"
                lines.append(f"    {outcome} ${r['pnl']:+.2f} (conv {r['conviction']:.2f})")
        return "\n".join(lines) if len(lines) > 1 else ""

    async def _enrich_pm_data(self, market_id: str) -> str:
        parts = []
        try:
            raw = await self.boba.call_tool("pm_get_top_holders", {"conditionId": market_id})
            data = json.loads(raw) if isinstance(raw, str) else raw
            count = len(data) if isinstance(data, list) else 0
            parts.append(f"PM holders: {count} large positions detected.")
        except Exception:
            pass
        try:
            raw = await self.boba.call_tool("pm_get_comments", {"eventId": market_id, "limit": 15})
            data = json.loads(raw) if isinstance(raw, str) else raw
            comments = data if isinstance(data, list) else data.get("comments", [])
            parts.append(f"PM comments: {len(comments)} recent.")
        except Exception:
            pass
        return "\n".join(parts)
