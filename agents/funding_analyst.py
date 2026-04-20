"""Funding/OI Analyst — derivatives market microstructure specialist.

Triggered by FUNDING_RATE_SPIKE and HL_WHALE_FLOW events. Interprets
funding extremes, OI changes, and whale flow imbalances.

Does NOT see: Polymarket data, wallet, other proposals.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.base import BaseSpecialist
from config import SPECIALIST_MODEL, TRADABLE_ASSETS
from db import save_proposal
from models import Direction, TradeProposal

logger = logging.getLogger(__name__)


class FundingAnalyst(BaseSpecialist):
    AGENT_ID = "funding_analyst"
    MODEL = SPECIALIST_MODEL

    SYSTEM_PROMPT = """\
You are the Funding/OI Analyst for SignalFlow, a multi-agent crypto trading system.
Your job: interpret derivatives market microstructure signals to find tradeable edges.

## Your Expertise
- Contrarian on funding extremes: crowd is long (positive funding) -> short bias;
  crowd is short (negative funding) -> long bias
- OI interpretation: rising OI + rising price = new longs; rising OI + falling price = new shorts
- Liquidation cascades: extreme OI + extreme funding = squeeze setup
- Cross-venue divergence (HL vs Binance funding) as arb signal
- Whale flow imbalances as directional pressure

## Data You Should Gather (use tools)
1. hl_get_predicted_funding — current funding rates
2. hl_get_markets — OI and volume context
3. hl_get_orderbook — bid/ask depth for execution quality estimate
4. hl_get_history — recent candles for price context

## Output Format
Return JSON (no markdown fences):
{
  "asset": "<BTC|ETH|SOL|DOGE|ARB|AVAX|LINK|SUI|INJ|OP|APT>",
  "direction": "long" | "short",
  "conviction": <float 0.0-1.0>,
  "edge_type": "funding" | "oi_flow",
  "reasoning": "<thesis — what the funding/OI data implies>",
  "suggested_risk_pct": <float 0.005-0.03>,
  "timeframe_hours": <float 1-12>,
  "invalidation": "<price level or condition>"
}

## Conviction Calibration
- 0.0-0.3: Normal funding range, no imbalance. Skip.
- 0.3-0.5: Mild funding extreme OR mild OI divergence. Low risk.
- 0.5-0.7: Funding extreme + OI confirms. Standard.
- 0.7-0.9: Extreme funding + whale flow aligned + squeeze setup. Strong.
- 0.9-1.0: Maximum extreme — clear liquidation cascade setup. Rare.

## Key Rules
- Contrarian by default on funding: positive funding = short bias, negative = long bias.
- Whale flow (when available) can override funding if massive and directional.
- You do NOT decide position size or see the portfolio.
"""

    async def handle(self, event_data: dict[str, Any]) -> list[dict]:
        """Process a FUNDING_RATE_SPIKE or HL_WHALE_FLOW event."""
        asset = event_data.get("asset", "").upper()
        if asset not in TRADABLE_ASSETS:
            return []

        event_type = event_data.get("_event_type", "funding")

        if event_type == "hl_whale_flow":
            return await self._handle_whale_flow(event_data, asset)
        return await self._handle_funding(event_data, asset)

    async def _handle_funding(self, event_data: dict, asset: str) -> list[dict]:
        hl_rate = event_data.get("hl_rate", 0)
        is_extreme = event_data.get("extreme", False)

        user_msg = (
            f"Analyze this funding rate signal:\n"
            f"- Asset: {asset}\n"
            f"- Hyperliquid predicted funding: {hl_rate*100:+.4f}%\n"
            f"- Extreme: {is_extreme}\n\n"
            f"Use tools to gather OI, volume, and orderbook context, "
            f"then return your JSON analysis."
        )

        return await self._run_analysis(user_msg, asset)

    async def _handle_whale_flow(self, event_data: dict, asset: str) -> list[dict]:
        direction = event_data.get("direction", "long")
        ratio = event_data.get("ratio", 0)
        buy_usd = event_data.get("buy_usd", 0)
        sell_usd = event_data.get("sell_usd", 0)
        oi_change = event_data.get("oi_change", 0)
        interpretation = event_data.get("interpretation", "")

        user_msg = (
            f"Analyze this Hyperliquid whale flow signal:\n"
            f"- Asset: {asset}\n"
            f"- Whale direction: {direction}\n"
            f"- Buy/sell ratio: {ratio:.2f}x\n"
            f"- Buy volume: ${buy_usd:,.0f}\n"
            f"- Sell volume: ${sell_usd:,.0f}\n"
            f"- OI change: {oi_change*100:+.1f}%\n"
            f"- Interpretation: {interpretation}\n\n"
            f"Use tools to check funding rates and recent price action, "
            f"then return your JSON analysis."
        )

        return await self._run_analysis(user_msg, asset)

    async def _run_analysis(self, user_msg: str, fallback_asset: str) -> list[dict]:
        try:
            result_text = await self.run_tool_loop(user_msg)
            parsed = self.extract_json(result_text)
            if parsed is None:
                logger.warning("[%s] Could not parse JSON", self.AGENT_ID)
                return []

            proposal = TradeProposal(
                agent_id=self.AGENT_ID,
                asset=(parsed.get("asset", fallback_asset) or fallback_asset).upper(),
                direction=Direction(parsed.get("direction", "long")),
                conviction=float(parsed.get("conviction", 0)),
                edge_type=parsed.get("edge_type", "funding"),
                reasoning=parsed.get("reasoning", ""),
                suggested_risk_pct=float(parsed.get("suggested_risk_pct", 0.015)),
                timeframe_hours=float(parsed.get("timeframe_hours", 4.0)),
                invalidation=parsed.get("invalidation", ""),
            )

            if proposal.asset not in TRADABLE_ASSETS:
                proposal.asset = fallback_asset

            proposal = save_proposal(proposal)
            logger.info(
                "[%s] Proposal #%d: %s %s conv=%.2f edge=%s",
                self.AGENT_ID, proposal.id, proposal.direction.value,
                proposal.asset, proposal.conviction, proposal.edge_type,
            )
            return [proposal.model_dump()]

        except Exception:
            logger.exception("[%s] Failed to analyze", self.AGENT_ID)
            return []
