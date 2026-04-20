"""Execution Specialist — optimal trade execution agent.

Takes approved proposals from the orchestrator and executes them on
Hyperliquid via Boba MCP. Handles sizing, orderbook checks, SL/TP placement,
and fill confirmation.

Does NOT decide: direction, asset, conviction (all given by approved proposal).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from agents.base import BaseSpecialist
from config import (
    SPECIALIST_MODEL,
    PAPER_WALLET_STARTING_BALANCE,
)
from db import (
    get_open_positions,
    get_stats,
    save_position,
    save_signal,
    save_analysis,
    save_signal_attribution,
    update_position,
    update_proposal,
)
from models import (
    Analysis,
    Direction,
    Position,
    ProposalStatus,
    Signal,
    TradeProposal,
)
from risk import (
    calculate_position_size_v2,
    can_open_position,
    can_open_position_for_asset,
    check_orderbook_liquidity,
    check_trade_cooldown,
    clamp_leverage,
    compute_atr,
    compute_stop_take_atr,
    confirm_fill_and_track_slippage,
)

logger = logging.getLogger(__name__)


class ExecutionSpecialist(BaseSpecialist):
    AGENT_ID = "executor"
    MODEL = SPECIALIST_MODEL

    SYSTEM_PROMPT = """\
You are the Execution Specialist for SignalFlow. Your job is optimal execution,
NOT trade direction (that's already decided). You receive approved proposals
with asset, direction, and risk allocation. Your tasks:
1. Check orderbook depth vs order size
2. Confirm fills and track slippage
3. Report execution quality back
"""

    async def handle(self, event_data: dict[str, Any]) -> list[dict]:
        """Execute an approved proposal. Returns position dict or empty list."""
        proposal = event_data.get("proposal")
        if proposal is None:
            return []

        if isinstance(proposal, dict):
            proposal = TradeProposal(**proposal)

        position = await self.execute_proposal(proposal)
        if position:
            return [position.model_dump()]
        return []

    async def execute_proposal(self, proposal: TradeProposal) -> Position | None:
        """Full v2-style execution pipeline for an approved proposal.

        Returns the opened Position, or None on failure.
        """
        asset = proposal.asset.upper()
        direction = proposal.direction
        allocated_risk_pct = proposal.allocated_risk_pct or proposal.suggested_risk_pct

        # Determine leverage from conviction
        leverage = clamp_leverage(3, proposal.conviction)

        # ── Risk gates ──
        allowed, reason = can_open_position(50, leverage)
        if not allowed:
            logger.warning("[%s] Risk blocked %s: %s", self.AGENT_ID, asset, reason)
            return None

        allowed, reason = can_open_position_for_asset(asset, direction)
        if not allowed:
            if reason.startswith("FLIP:"):
                # Close existing opposite position
                old_id = int(reason.split(":")[1])
                await self._close_position_on_exchange(asset)
                price = await self.get_asset_price(asset)
                if price > 0:
                    old_positions = get_open_positions()
                    old_p = next((p for p in old_positions if p.id == old_id), None)
                    if old_p:
                        if old_p.direction == Direction.LONG:
                            pnl = (price - old_p.entry_price) / old_p.entry_price * old_p.size_usd * old_p.leverage
                        else:
                            pnl = (old_p.entry_price - price) / old_p.entry_price * old_p.size_usd * old_p.leverage
                        from models import PositionStatus
                        update_position(old_id, status=PositionStatus.CLOSED, pnl=round(pnl, 2), closed_at=datetime.utcnow())
                        logger.info("[%s] FLIPPED #%d %s", self.AGENT_ID, old_id, asset)
            else:
                logger.warning("[%s] Asset blocked %s: %s", self.AGENT_ID, asset, reason)
                return None

        allowed, reason = check_trade_cooldown(asset)
        if not allowed:
            logger.info("[%s] Cooldown: %s", self.AGENT_ID, reason)
            return None

        # ── Get entry price ──
        entry_price = await self.get_asset_price(asset)
        if entry_price <= 0:
            logger.warning("[%s] No price for %s", self.AGENT_ID, asset)
            return None

        # ── Compute ATR + stops ──
        atr = await compute_atr(self.boba, asset)
        stop_loss, take_profit = await compute_stop_take_atr(
            self.boba, entry_price, direction, asset
        )

        # ── Sizing: orchestrator's risk allocation drives position size directly ──
        #
        # The old formula (risk$ / stop% × leverage) always produced huge notionals
        # that hit the cap, making every trade the same size. Instead, we use a
        # simpler, more intuitive approach:
        #
        #   size = wallet × allocated_risk_pct × conviction_multiplier
        #
        # This means:
        #   - 2% risk on $95 wallet, conv 0.70 → $95 × 0.02 × 3.5 = $6.65
        #   - 5% risk on $95 wallet, conv 0.70 → $95 × 0.05 × 3.5 = $16.6
        #   - 10% risk on $95 wallet, conv 0.90 → $95 × 0.10 × 4.5 = $42.7
        #   - 15% risk on $95 wallet, conv 0.95 → $95 × 0.15 × 5.0 = $71.3
        #
        # The conviction_multiplier scales from 2x (low conv) to 5x (exceptional).
        # This replaces the leveraged fixed-fractional formula that was always capped.

        stats = get_stats()
        wallet_balance = PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"]

        # Conviction multiplier: maps conviction to a sizing multiplier
        conv = proposal.conviction
        if conv >= 0.90:
            conv_mult = 5.0   # exceptional — go big
        elif conv >= 0.75:
            conv_mult = 4.0   # strong
        elif conv >= 0.60:
            conv_mult = 3.0   # moderate
        elif conv >= 0.45:
            conv_mult = 2.0   # speculative
        else:
            conv_mult = 1.5   # minimal

        size_usd = wallet_balance * allocated_risk_pct * conv_mult

        # Safety cap: never more than 70% of wallet in one trade
        max_per_trade = wallet_balance * 0.70
        size_usd = max(5.0, min(size_usd, max_per_trade))

        logger.info(
            "[%s] Sizing %s: wallet=$%.0f × risk=%.1f%% × conv_mult=%.1f → $%.0f",
            self.AGENT_ID, asset, wallet_balance, allocated_risk_pct * 100,
            conv_mult, size_usd,
        )

        # ── Orderbook check ──
        is_liquid, est_slippage, liq_reason = await check_orderbook_liquidity(
            self.boba, asset, size_usd, direction
        )
        if not is_liquid:
            logger.warning("[%s] Orderbook rejected %s: %s", self.AGENT_ID, asset, liq_reason)
            return None

        # ── Execute on Hyperliquid ──
        side = "buy" if direction == Direction.LONG else "sell"

        try:
            await self.boba.call_tool("hl_update_leverage", {
                "coin": asset, "leverage": leverage, "mode": "cross",
            })
        except Exception:
            logger.exception("[%s] hl_update_leverage failed for %s", self.AGENT_ID, asset)
            return None

        try:
            order_result = await self.boba.call_tool("hl_place_order", {
                "coin": asset, "side": side, "size": size_usd, "type": "market",
            })
            logger.info("[%s] Order result: %s", self.AGENT_ID, str(order_result)[:200])
        except Exception:
            logger.exception("[%s] Market order failed for %s", self.AGENT_ID, asset)
            return None

        # ── Confirm fill ──
        actual_price, slippage = await confirm_fill_and_track_slippage(
            self.boba, asset, entry_price, direction
        )
        if actual_price and actual_price > 0:
            entry_price = actual_price
            stop_loss, take_profit = await compute_stop_take_atr(
                self.boba, actual_price, direction, asset
            )

        # ── SL/TP orders (best-effort) ──
        sl_side = "sell" if direction == Direction.LONG else "buy"
        for label, order_type, trigger in [("SL", "stop", stop_loss), ("TP", "take_profit", take_profit)]:
            try:
                await self.boba.call_tool("hl_place_order", {
                    "coin": asset, "side": sl_side, "size": size_usd,
                    "type": order_type, "triggerPrice": str(trigger),
                })
            except Exception as e:
                logger.warning("[%s] %s order failed for %s: %s", self.AGENT_ID, label, asset, e)

        # ── Create synthetic signal + analysis for DB compatibility ──
        synthetic_signal = save_signal(Signal(
            market_id=f"v3_{proposal.agent_id}_{proposal.id}",
            market_question=f"v3 proposal #{proposal.id} from {proposal.agent_id}: {proposal.reasoning[:100]}",
            current_price=entry_price,
            price_change_pct=0.0,
            timeframe_minutes=int(proposal.timeframe_hours * 60),
            category=f"v3_{proposal.edge_type}",
        ))
        analysis = save_analysis(Analysis(
            signal_id=synthetic_signal.id or 0,
            reasoning=proposal.reasoning,
            conviction_score=proposal.conviction,
            suggested_direction=direction,
            suggested_asset=asset,
            suggested_size_usd=size_usd,
            risk_notes=f"v3 proposal_id={proposal.id} agent={proposal.agent_id}",
        ))

        # ── Save position with v3 metadata ──
        position = Position(
            analysis_id=analysis.id or 0,
            asset=asset,
            direction=direction,
            entry_price=entry_price,
            size_usd=size_usd,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        position = save_position(position)

        # Set v3 agent_id + proposal_id and v2 chandelier fields
        update_position(
            position.id,
            extreme_price=entry_price,
            atr_at_entry=atr if atr else None,
        )
        # Update agent_id and proposal_id directly (not in update_position params yet)
        from db import _get_conn
        conn = _get_conn()
        conn.execute(
            "UPDATE positions SET agent_id = ?, proposal_id = ? WHERE id = ?",
            (proposal.agent_id, proposal.id, position.id),
        )
        conn.commit()

        # Mark proposal as executed
        update_proposal(
            proposal.id,
            status=ProposalStatus.EXECUTED,
            executed_at=datetime.utcnow(),
        )

        slippage_note = f" slippage={slippage:+.3%}" if slippage is not None else ""
        logger.info(
            "[%s] OPENED %s %s $%.0f @ %.4f (SL: %.2f, TP: %.2f%s) proposal=#%d",
            self.AGENT_ID, direction.value, asset, size_usd, entry_price,
            stop_loss, take_profit, slippage_note, proposal.id,
        )
        return position

    async def _close_position_on_exchange(self, asset: str) -> bool:
        try:
            result = await self.boba.call_tool("hl_close_position", {"coin": asset})
            logger.info("[%s] Closed %s: %s", self.AGENT_ID, asset, str(result)[:200])
            return True
        except Exception:
            logger.debug("[%s] Close failed for %s", self.AGENT_ID, asset, exc_info=True)
            return False
