"""Trend Analyst — pure price-structure specialist.

Called by the orchestrator on-demand (not event-triggered). Produces
RegimeAssessments and optional TradeProposals on breakout/reversal setups.

Does NOT see: PM signals, funding, wallet.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.base import BaseSpecialist
from config import SPECIALIST_MODEL, TRADABLE_ASSETS
from db import save_proposal, save_regime
from models import Direction, RegimeAssessment, RegimeType, TradeProposal

logger = logging.getLogger(__name__)


class TrendAnalyst(BaseSpecialist):
    AGENT_ID = "trend_analyst"
    MODEL = SPECIALIST_MODEL

    SYSTEM_PROMPT = """\
You are the Trend Analyst for SignalFlow, a multi-agent crypto trading system.
You are a pure price-structure analyst — no sentiment, no fundamentals.

## Your Expertise
- EMA alignment: 8/21 on 1h timeframe, trend direction and strength
- Support/resistance from recent highs/lows
- ATR expansion/contraction as volatility regime signal
- Identifying: trending (trade with momentum), ranging (mean-revert at extremes),
  volatile (reduce size)

## Data You Should Gather (use tools)
1. hl_get_history — 1h candles (last 30-50 periods for EMA calculation)
2. hl_get_markets — 24h change, volume context

## Output Format
You MUST return TWO JSON objects separated by a newline.

First, the regime assessment:
{
  "type": "regime",
  "asset": "<ASSET>",
  "regime": "trending_up" | "trending_down" | "ranging" | "volatile",
  "strength": <float 0.0-1.0>,
  "support": <float price level>,
  "resistance": <float price level>,
  "atr_expanding": true | false,
  "recommendation": "<brief: trend trades only / mean-revert / reduce size>"
}

Second, ONLY if a clear breakout or reversal setup exists, a trade proposal:
{
  "type": "proposal",
  "asset": "<ASSET>",
  "direction": "long" | "short",
  "conviction": <float 0.0-1.0>,
  "edge_type": "momentum" | "mean_revert",
  "reasoning": "<price structure thesis>",
  "suggested_risk_pct": <float 0.005-0.03>,
  "timeframe_hours": <float 2-12>,
  "invalidation": "<price level>"
}

If no clear setup, return ONLY the regime assessment.

## Key Rules
- You are the REGIME expert. The orchestrator uses your regime to adjust all sizing.
- Only propose trades on clear breakouts (EMA crossover + ATR expansion) or
  extreme mean-reversion (price at major S/R with ATR contraction).
- Be conservative with proposals — your main value is the regime assessment.
"""

    async def handle(self, event_data: dict[str, Any]) -> list[dict]:
        """Analyze an asset's price structure. Returns regime + optional proposal."""
        asset = event_data.get("asset", "").upper()
        if asset not in TRADABLE_ASSETS:
            return []

        user_msg = (
            f"Analyze the price structure and trend regime for {asset}.\n"
            f"Use hl_get_history to fetch 1h candles and hl_get_markets for context.\n"
            f"Return the regime assessment (always) and a trade proposal (only if setup exists)."
        )

        try:
            result_text = await self.run_tool_loop(user_msg)
            results = []

            # Try to extract multiple JSON objects
            remaining = result_text
            while remaining:
                parsed = self.extract_json(remaining)
                if parsed is None:
                    break

                obj_type = parsed.get("type", "")

                if obj_type == "regime":
                    regime = RegimeAssessment(
                        asset=asset,
                        regime=RegimeType(parsed.get("regime", "ranging")),
                        strength=float(parsed.get("strength", 0.5)),
                        support=parsed.get("support"),
                        resistance=parsed.get("resistance"),
                        atr_expanding=bool(parsed.get("atr_expanding", False)),
                        recommendation=parsed.get("recommendation", ""),
                    )
                    regime = save_regime(regime)
                    logger.info(
                        "[%s] Regime %s: %s strength=%.2f S=%.2f R=%.2f",
                        self.AGENT_ID, asset, regime.regime.value,
                        regime.strength,
                        regime.support or 0, regime.resistance or 0,
                    )
                    results.append({"type": "regime", **regime.model_dump()})

                elif obj_type == "proposal":
                    proposal = TradeProposal(
                        agent_id=self.AGENT_ID,
                        asset=asset,
                        direction=Direction(parsed.get("direction", "long")),
                        conviction=float(parsed.get("conviction", 0)),
                        edge_type=parsed.get("edge_type", "momentum"),
                        reasoning=parsed.get("reasoning", ""),
                        suggested_risk_pct=float(parsed.get("suggested_risk_pct", 0.015)),
                        timeframe_hours=float(parsed.get("timeframe_hours", 4.0)),
                        invalidation=parsed.get("invalidation", ""),
                    )
                    proposal = save_proposal(proposal)
                    logger.info(
                        "[%s] Proposal #%d: %s %s conv=%.2f",
                        self.AGENT_ID, proposal.id,
                        proposal.direction.value, proposal.asset, proposal.conviction,
                    )
                    results.append(proposal.model_dump())

                # Move past the parsed JSON to find the next one
                json_str = json.dumps(parsed)
                idx = remaining.find("{")
                if idx == -1:
                    break
                # Find the end of this JSON object
                depth = 0
                end_idx = idx
                for i in range(idx, len(remaining)):
                    if remaining[i] == "{":
                        depth += 1
                    elif remaining[i] == "}":
                        depth -= 1
                        if depth == 0:
                            end_idx = i + 1
                            break
                remaining = remaining[end_idx:]

            return results

        except Exception:
            logger.exception("[%s] Failed to analyze trend for %s", self.AGENT_ID, asset)
            return []

    async def assess_regime(self, asset: str) -> RegimeAssessment | None:
        """Convenience method: run handle and return just the regime."""
        results = await self.handle({"asset": asset})
        for r in results:
            if r.get("type") == "regime":
                return RegimeAssessment(**{k: v for k, v in r.items() if k != "type"})
        return None
