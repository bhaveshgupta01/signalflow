"""Portfolio Manager / Orchestrator — the brain of v3.

Batches pending proposals every 30-60s, reads the full portfolio state,
and decides which proposals to approve/reject/close. Uses gemini-2.5-flash
(the smarter model) for strategic reasoning.

Sees: ALL pending proposals, wallet balance, ALL open positions,
per-agent performance, regime assessments, drawdown state.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from google import genai

from agents.base import BaseSpecialist
from agents.executor import ExecutionSpecialist
from agents.trend_analyst import TrendAnalyst
from config import (
    ORCHESTRATOR_MODEL,
    ORCHESTRATOR_BATCH_INTERVAL,
    PAPER_WALLET_STARTING_BALANCE,
    PROPOSAL_EXPIRY_MINUTES,
    TRADABLE_ASSETS,
)
from db import (
    compute_agent_stats,
    expire_old_proposals,
    get_approved_proposals,
    get_latest_regime,
    get_open_positions,
    get_pending_proposals,
    get_stats,
    update_position,
    update_proposal,
)
from mcp_client import BobaClient
from models import (
    Direction,
    PositionStatus,
    ProposalStatus,
    TradeProposal,
)

logger = logging.getLogger(__name__)


class Orchestrator(BaseSpecialist):
    AGENT_ID = "orchestrator"
    MODEL = ORCHESTRATOR_MODEL

    SYSTEM_PROMPT = """\
You are the Portfolio Manager for SignalFlow, a multi-agent crypto trading system.
You are the ONLY agent that sees the full picture: all pending proposals, the wallet,
all open positions, per-agent performance history, and market regime.

## Your Role
- Decide WHICH proposals to APPROVE (and at what risk allocation)
- Decide which to REJECT (and why)
- Decide whether to CLOSE existing positions to free margin
- Ensure portfolio diversification (not over-concentrated in one asset/direction)

## Decision Framework

### Approval Criteria
1. Conviction strength — higher is better, but context matters
2. Edge quality — "deep" edges (multi-factor) > "shallow" (single signal)
3. Diversification — does this ADD diversity or CONCENTRATE risk?
4. Agent track record — which agent has been most profitable? Weight their proposals higher.
5. Regime context — if Trend says "ranging", fade PM moves; if "trending", follow momentum
6. Drawdown state — in drawdown, be MORE selective (raise conviction threshold)

### Risk Allocation (YOU CONTROL HOW MUCH CAPITAL GOES INTO EACH TRADE)
This is your most important decision. allocated_risk_pct controls position size:
- 1% risk on $90 wallet with 2.5% stop and 3x leverage = ~$10 position
- 5% risk = ~$54 position
- 10% risk = ~$100 position (big bet)

Use this scale based on conviction + edge quality + agent track record:
- 1-2% risk: Speculative. Single factor, unproven agent, or mild conviction.
- 3-5% risk: Standard. Multi-factor edge, decent agent track record, moderate conviction.
- 5-8% risk: Strong. High conviction + proven agent + regime confirmation. Go bigger.
- 8-15% risk: Exceptional. Near-certain setup, best agent, everything aligns.
  Use this rarely — but when you see it, SIZE UP. Missing a 90% edge is worse
  than taking a small loss on a 60% edge.

Scale DOWN in drawdown: if drawdown > 15%, halve all allocations.
Scale DOWN if correlated with existing positions.

### Portfolio Rules
- Max 8 concurrent positions
- No more than 50% of portfolio in one asset class direction
- If 2+ specialists agree on same asset+direction = stronger signal — SIZE UP
- Duplicative proposals: approve the higher-conviction one, reject the rest
- You CAN close weak positions to free capital for a stronger opportunity

## Input Format
You will receive a JSON context object with:
- pending_proposals: list of proposals awaiting your decision
- wallet_balance: current USD balance
- open_positions: list of active positions with unrealized PnL
- agent_performance: per-agent 7d stats (win_rate, total_pnl)
- regime_assessments: latest regime per asset
- drawdown_pct: current drawdown from peak

## Output Format
Return a JSON array of decisions:
[
  {"proposal_id": 42, "action": "approve", "allocated_risk_pct": 0.02,
   "reason": "Strong PM + funding alignment, no existing exposure"},
  {"proposal_id": 43, "action": "reject",
   "reason": "Already 40% exposed to alts, would over-concentrate"},
  {"action": "close", "position_id": 235,
   "reason": "Aged 10h, trend weakening, free margin for new opportunities"}
]

## Key Rules
- ALWAYS return valid JSON array (no markdown fences).
- Every pending proposal MUST get either "approve" or "reject".
- You MAY include "close" decisions for existing positions.
- Reasons must be specific and actionable.
- When in doubt, reject — capital preservation > missed opportunity.
"""

    def __init__(
        self,
        client: genai.Client,
        boba: BobaClient,
        executor: ExecutionSpecialist,
        trend_analyst: TrendAnalyst,
    ) -> None:
        super().__init__(client, boba)
        self.executor = executor
        self.trend_analyst = trend_analyst
        self._running = False

    async def run_loop(self) -> None:
        """Main orchestrator loop — batch proposals every N seconds."""
        self._running = True
        self._regime_refresh_counter = 0
        logger.info("[%s] Orchestrator loop started (interval=%ds)", self.AGENT_ID, ORCHESTRATOR_BATCH_INTERVAL)

        while self._running:
            try:
                await self._batch_cycle()
            except Exception:
                logger.exception("[%s] Batch cycle error", self.AGENT_ID)

            # Refresh regime assessments every ~10 minutes (20 cycles × 30s)
            self._regime_refresh_counter += 1
            if self._regime_refresh_counter >= 20:
                self._regime_refresh_counter = 0
                await self._refresh_regimes()

            await asyncio.sleep(ORCHESTRATOR_BATCH_INTERVAL)

    async def _refresh_regimes(self) -> None:
        """Proactively refresh regime assessments for all tradable assets."""
        from config import TRADABLE_ASSETS
        # Only refresh the most commonly traded assets to save API calls
        key_assets = ["BTC", "ETH", "SOL", "DOGE"]
        for asset in key_assets:
            try:
                regime = get_latest_regime(asset)
                if regime:
                    age_hours = (datetime.utcnow() - regime.created_at).total_seconds() / 3600
                    if age_hours < 2:
                        continue  # still fresh
                r = await asyncio.wait_for(
                    self.trend_analyst.assess_regime(asset), timeout=30.0
                )
                if r:
                    logger.info(
                        "[%s] Regime refresh %s: %s str=%.2f",
                        self.AGENT_ID, asset, r.regime.value, r.strength,
                    )
            except Exception:
                logger.debug("[%s] Regime refresh failed for %s", self.AGENT_ID, asset, exc_info=True)

    def stop(self) -> None:
        self._running = False

    async def _batch_cycle(self) -> None:
        """One orchestrator cycle: expire old, read proposals, decide, execute."""
        # Expire stale proposals
        expired = expire_old_proposals(PROPOSAL_EXPIRY_MINUTES)
        if expired:
            logger.info("[%s] Expired %d stale proposals", self.AGENT_ID, expired)

        # Get pending proposals
        proposals = get_pending_proposals()
        if not proposals:
            return

        logger.info("[%s] Processing %d pending proposals", self.AGENT_ID, len(proposals))

        # Build full context for orchestrator decision
        context = await self._build_context(proposals)

        # Ask Gemini for decisions
        user_msg = (
            f"Here is the current portfolio state and pending proposals.\n"
            f"Make your approval/rejection/close decisions.\n\n"
            f"```json\n{json.dumps(context, indent=2, default=str)}\n```"
        )

        try:
            result_text = await self.run_tool_loop(user_msg, max_rounds=3)
            decisions = self.extract_json(result_text)
        except Exception:
            logger.exception("[%s] Gemini decision failed", self.AGENT_ID)
            return

        if isinstance(decisions, dict):
            decisions = [decisions]
        if not isinstance(decisions, list):
            logger.warning("[%s] Invalid decision format: %s", self.AGENT_ID, type(decisions))
            return

        # Process decisions
        now = datetime.utcnow()
        approved_proposals: list[TradeProposal] = []

        for decision in decisions:
            action = decision.get("action", "")
            reason = decision.get("reason", "")

            if action == "approve":
                proposal_id = decision.get("proposal_id")
                risk_pct = float(decision.get("allocated_risk_pct", 0.015))
                # Clamp risk — allow up to 15% for exceptional setups
                risk_pct = max(0.005, min(0.15, risk_pct))

                proposal = next((p for p in proposals if p.id == proposal_id), None)
                if proposal:
                    update_proposal(
                        proposal_id,
                        status=ProposalStatus.APPROVED,
                        allocated_risk_pct=risk_pct,
                        orchestrator_reason=reason,
                        decided_at=now,
                    )
                    proposal.status = ProposalStatus.APPROVED
                    proposal.allocated_risk_pct = risk_pct
                    approved_proposals.append(proposal)
                    logger.info(
                        "[%s] APPROVED #%d %s %s risk=%.1f%%: %s",
                        self.AGENT_ID, proposal_id, proposal.asset,
                        proposal.direction.value, risk_pct * 100, reason,
                    )

            elif action == "reject":
                proposal_id = decision.get("proposal_id")
                if proposal_id:
                    update_proposal(
                        proposal_id,
                        status=ProposalStatus.REJECTED,
                        orchestrator_reason=reason,
                        decided_at=now,
                    )
                    logger.info("[%s] REJECTED #%d: %s", self.AGENT_ID, proposal_id, reason)

            elif action == "close":
                position_id = decision.get("position_id")
                if position_id:
                    await self._close_position(position_id, reason)

        # Execute approved proposals
        for proposal in approved_proposals:
            try:
                position = await self.executor.execute_proposal(proposal)
                if position:
                    logger.info(
                        "[%s] Executed proposal #%d -> position #%d",
                        self.AGENT_ID, proposal.id, position.id,
                    )
            except Exception:
                logger.exception(
                    "[%s] Execution failed for proposal #%d", self.AGENT_ID, proposal.id,
                )

    async def nudge(self, proposal: TradeProposal) -> None:
        """Immediately process a high-conviction proposal without waiting for batch."""
        logger.info(
            "[%s] NUDGE: high-conviction proposal #%d (%.2f) from %s",
            self.AGENT_ID, proposal.id, proposal.conviction, proposal.agent_id,
        )
        await self._batch_cycle()

    async def _build_context(self, proposals: list[TradeProposal]) -> dict:
        """Build the full context dict the orchestrator LLM sees."""
        stats = get_stats()
        wallet_balance = PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"]
        open_positions = get_open_positions()
        peak_balance = max(PAPER_WALLET_STARTING_BALANCE, wallet_balance)
        drawdown_pct = (peak_balance - wallet_balance) / peak_balance if peak_balance > 0 else 0

        # Per-agent performance
        agent_ids = set(p.agent_id for p in proposals)
        agent_perf = {}
        for aid in agent_ids:
            agent_perf[aid] = compute_agent_stats(aid, days=7)

        # Regime assessments for proposed assets + open position assets
        proposed_assets = set(p.asset for p in proposals)
        for pos in open_positions:
            proposed_assets.add(pos.asset)
        regimes = {}
        for asset in proposed_assets:
            regime = get_latest_regime(asset)
            # Refresh if missing OR stale (>4 hours old)
            is_stale = False
            if regime:
                age_hours = (datetime.utcnow() - regime.created_at).total_seconds() / 3600
                is_stale = age_hours > 4
            if regime and not is_stale:
                regimes[asset] = {
                    "regime": regime.regime.value,
                    "strength": regime.strength,
                    "support": regime.support,
                    "resistance": regime.resistance,
                    "atr_expanding": regime.atr_expanding,
                    "recommendation": regime.recommendation,
                }
            else:
                # Request fresh regime from trend analyst
                try:
                    r = await asyncio.wait_for(
                        self.trend_analyst.assess_regime(asset), timeout=30.0
                    )
                    if r:
                        regimes[asset] = {
                            "regime": r.regime.value,
                            "strength": r.strength,
                            "support": r.support,
                            "resistance": r.resistance,
                            "atr_expanding": r.atr_expanding,
                            "recommendation": r.recommendation,
                        }
                except Exception:
                    logger.debug("[%s] Regime fetch failed for %s", self.AGENT_ID, asset)

        # Compute current asset exposure
        exposure = {}
        for pos in open_positions:
            key = f"{pos.asset}_{pos.direction.value}"
            exposure[key] = exposure.get(key, 0) + pos.size_usd

        return {
            "pending_proposals": [
                {
                    "proposal_id": p.id,
                    "agent_id": p.agent_id,
                    "asset": p.asset,
                    "direction": p.direction.value,
                    "conviction": p.conviction,
                    "edge_type": p.edge_type,
                    "reasoning": p.reasoning[:300],
                    "suggested_risk_pct": p.suggested_risk_pct,
                    "timeframe_hours": p.timeframe_hours,
                    "invalidation": p.invalidation,
                }
                for p in proposals
            ],
            "wallet_balance": round(wallet_balance, 2),
            "drawdown_pct": round(drawdown_pct, 4),
            "open_positions": [
                {
                    "id": pos.id,
                    "asset": pos.asset,
                    "direction": pos.direction.value,
                    "entry_price": pos.entry_price,
                    "size_usd": pos.size_usd,
                    "pnl": pos.pnl,
                    "age_hours": round((datetime.utcnow() - pos.opened_at).total_seconds() / 3600, 1),
                }
                for pos in open_positions
            ],
            "exposure_by_asset": exposure,
            "agent_performance": agent_perf,
            "regime_assessments": regimes,
            "portfolio_stats": stats,
        }

    async def _close_position(self, position_id: int, reason: str) -> None:
        """Close an existing position by orchestrator decision."""
        positions = get_open_positions()
        pos = next((p for p in positions if p.id == position_id), None)
        if not pos:
            logger.warning("[%s] Position #%d not found for close", self.AGENT_ID, position_id)
            return

        try:
            await self.boba.call_tool("hl_close_position", {"coin": pos.asset})
        except Exception:
            logger.warning("[%s] Close failed for #%d %s", self.AGENT_ID, position_id, pos.asset)
            return

        price = await self.get_asset_price(pos.asset)
        if price > 0:
            if pos.direction == Direction.LONG:
                pnl = (price - pos.entry_price) / pos.entry_price * pos.size_usd * pos.leverage
            else:
                pnl = (pos.entry_price - price) / pos.entry_price * pos.size_usd * pos.leverage
            pnl = round(pnl, 2)
        else:
            pnl = pos.pnl

        status = PositionStatus.CLOSED if pnl >= 0 else PositionStatus.STOPPED
        update_position(position_id, status=status, pnl=pnl, closed_at=datetime.utcnow())
        logger.info(
            "[%s] CLOSED #%d %s %s PnL=$%+.2f: %s",
            self.AGENT_ID, position_id, pos.direction.value, pos.asset, pnl, reason,
        )

    async def handle(self, event_data: dict[str, Any]) -> list[dict]:
        """Not used directly — orchestrator runs via run_loop or nudge."""
        return []
