"""v3 event router — thin dispatcher that routes events to specialist agents.

Replaces the monolithic agent.py handle_event() when STRATEGY_VERSION=3.
The v2 agent.py is preserved for rollback (STRATEGY_VERSION=2).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from google import genai

from agents.executor import ExecutionSpecialist
from agents.funding_analyst import FundingAnalyst
from agents.orchestrator import Orchestrator
from agents.pm_analyst import PMAnalyst
from agents.trend_analyst import TrendAnalyst
from config import HIGH_CONVICTION_THRESHOLD, PAPER_WALLET_STARTING_BALANCE
from db import (
    get_open_positions,
    get_position_extra,
    get_stats,
    save_decision,
    save_position_snapshot,
    save_wallet_snapshot,
    update_position,
)
from event_bus import Event, EventBus, TriggerType
from mcp_client import BobaClient
from models import (
    AgentDecision,
    Direction,
    PositionSnapshot,
    PositionStatus,
    WalletSnapshot,
)
from risk import chandelier_stop
from config import MAX_POSITION_AGE_HOURS

logger = logging.getLogger(__name__)


class V3EventRouter:
    """Routes trigger events to specialist agents and runs the risk monitor.

    Architecture:
      event -> router -> specialist -> proposal (DB) -> orchestrator -> executor
    """

    def __init__(
        self,
        client: genai.Client,
        boba: BobaClient,
        bus: EventBus,
    ) -> None:
        self.client = client
        self.boba = boba
        self.bus = bus

        # Create specialist agents
        self.pm_analyst = PMAnalyst(client, boba)
        self.funding_analyst = FundingAnalyst(client, boba)
        self.trend_analyst = TrendAnalyst(client, boba)
        self.executor = ExecutionSpecialist(client, boba)
        self.orchestrator = Orchestrator(client, boba, self.executor, self.trend_analyst)

    async def handle_event(self, event: Event) -> None:
        """Route event to the appropriate specialist, then run risk monitor."""
        cycle_id = datetime.utcnow().strftime("%H%M%S") + f"_{event.trigger.value[:8]}"
        decision = AgentDecision(cycle_id=cycle_id, timestamp=datetime.utcnow())

        proposals = []

        if event.trigger == TriggerType.POLYMARKET_MOVE:
            signal = event.data.get("signal")
            if signal:
                decision.signals_detected = 1
                proposals = await self.pm_analyst.handle({"signal": signal})
                decision.analyses_produced = len(proposals)

        elif event.trigger == TriggerType.FUNDING_RATE_SPIKE:
            decision.signals_detected = 1
            event_data = {**event.data, "_event_type": "funding"}
            proposals = await self.funding_analyst.handle(event_data)
            decision.analyses_produced = len(proposals)

        elif event.trigger == TriggerType.HL_WHALE_FLOW:
            decision.signals_detected = 1
            event_data = {**event.data, "_event_type": "hl_whale_flow"}
            proposals = await self.funding_analyst.handle(event_data)
            decision.analyses_produced = len(proposals)

        elif event.trigger == TriggerType.KOL_WHALE_TRADE:
            kol_signal = event.data.get("kol_signal")
            if kol_signal:
                logger.info(
                    "[v3] KOL event: %s %s %s $%.0f",
                    kol_signal.kol_name, kol_signal.direction.value,
                    kol_signal.asset, kol_signal.trade_size_usd,
                )

        elif event.trigger == TriggerType.TOKEN_DISCOVERY:
            logger.info("[v3] Token discovery: %s", event.data.get("symbol", ""))
            decision.signals_detected = 1

        elif event.trigger == TriggerType.CROSS_CHAIN_OPPORTUNITY:
            logger.info("[v3] Cross-chain: %s", event.data.get("asset", ""))

        elif event.trigger == TriggerType.PORTFOLIO_UPDATE:
            logger.info("[v3] Portfolio update")

        # Nudge orchestrator immediately for any actionable proposal
        # (don't wait for the 30s batch timer — proposals expire fast)
        if proposals:
            from models import TradeProposal
            for p in proposals:
                conviction = p.get("conviction", 0)
                agent_id = p.get("agent_id", "")
                # Nudge if: conviction >= threshold OR from a proven agent (funding_analyst)
                should_nudge = (
                    conviction >= HIGH_CONVICTION_THRESHOLD
                    or agent_id == "funding_analyst"
                )
                if should_nudge:
                    try:
                        tp = TradeProposal(**p)
                        await self.orchestrator.nudge(tp)
                        decision.trades_executed += 1
                    except Exception:
                        logger.debug("[v3] Nudge failed", exc_info=True)

        # Always run risk monitor
        await self._risk_monitor()

        # Save decision + snapshot
        decision.reasoning_summary = (
            f"[v3 {event.trigger.value}] proposals={len(proposals)} "
            f"trades={decision.trades_executed}"
        )
        save_decision(decision)
        self._save_snapshot()

    async def _risk_monitor(self) -> None:
        """Mechanical position management — no LLM.

        Same as v2 _manage_positions:
          1. Mark-to-market PnL + snapshot
          2. Hard SL -> STOPPED
          3. Hard TP -> CLOSED
          4. Chandelier trailing stop
          5. 12h max age -> close
        """
        open_pos = get_open_positions()
        if not open_pos:
            return

        now = datetime.utcnow()

        for p in open_pos:
            price = await self._get_price(p.asset)
            if price <= 0:
                continue

            # PnL
            if p.direction == Direction.LONG:
                pnl = (price - p.entry_price) / p.entry_price * p.size_usd * p.leverage
            else:
                pnl = (p.entry_price - price) / p.entry_price * p.size_usd * p.leverage
            pnl = round(pnl, 2)

            update_position(p.id, pnl=pnl)
            save_position_snapshot(PositionSnapshot(
                position_id=p.id, asset=p.asset,
                current_price=price, unrealized_pnl=pnl,
            ))

            age_hours = (now - p.opened_at).total_seconds() / 3600

            # Hard SL
            hit_sl = (p.direction == Direction.LONG and price <= p.stop_loss) or \
                     (p.direction == Direction.SHORT and price >= p.stop_loss)
            if hit_sl:
                await self._close_on_exchange(p.asset)
                update_position(p.id, status=PositionStatus.STOPPED, pnl=pnl, closed_at=now)
                logger.info("[v3-risk] STOP #%d %s PnL=$%+.2f", p.id, p.asset, pnl)
                continue

            # Hard TP
            hit_tp = (p.direction == Direction.LONG and price >= p.take_profit) or \
                     (p.direction == Direction.SHORT and price <= p.take_profit)
            if hit_tp:
                await self._close_on_exchange(p.asset)
                update_position(p.id, status=PositionStatus.CLOSED, pnl=pnl, closed_at=now)
                logger.info("[v3-risk] TP #%d %s PnL=$%+.2f", p.id, p.asset, pnl)
                continue

            # Chandelier trailing stop
            extra = get_position_extra(p.id)
            prev_extreme = extra.get("extreme_price") or p.entry_price
            atr = extra.get("atr_at_entry")

            if p.direction == Direction.LONG:
                new_extreme = max(prev_extreme, price)
            else:
                new_extreme = min(prev_extreme, price)
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
                        "[v3-risk] CHANDELIER #%d %s SL %.4f->%.4f",
                        p.id, p.asset, p.stop_loss, new_sl,
                    )

            # 12h max age
            if age_hours >= MAX_POSITION_AGE_HOURS:
                await self._close_on_exchange(p.asset)
                status = PositionStatus.CLOSED if pnl >= 0 else PositionStatus.STOPPED
                update_position(p.id, status=status, pnl=pnl, closed_at=now)
                logger.info("[v3-risk] MAX-AGE #%d %s %.1fh PnL=$%+.2f", p.id, p.asset, age_hours, pnl)

    async def _get_price(self, asset: str) -> float:
        """Fetch current price — shared helper."""
        import json
        try:
            raw = await self.boba.call_tool("hl_get_asset", {"coin": asset})
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, dict):
                mark = data.get("mark") or data.get("markPx") or data.get("price") or 0
                return float(str(mark).replace(",", ""))
        except Exception:
            pass
        return 0.0

    async def _close_on_exchange(self, asset: str) -> bool:
        try:
            await self.boba.call_tool("hl_close_position", {"coin": asset})
            return True
        except Exception:
            return False

    def _save_snapshot(self) -> None:
        stats = get_stats()
        save_wallet_snapshot(WalletSnapshot(
            balance=PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"],
            total_pnl=stats["total_pnl"],
            open_positions=len(get_open_positions()),
        ))
