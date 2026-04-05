"""Event bus — async queue connecting triggers to the agent."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TriggerType(str, Enum):
    POLYMARKET_MOVE = "polymarket_move"
    KOL_WHALE_TRADE = "kol_whale_trade"
    FUNDING_RATE_SPIKE = "funding_rate_spike"
    TOKEN_DISCOVERY = "token_discovery"
    CROSS_CHAIN_OPPORTUNITY = "cross_chain_opportunity"
    PORTFOLIO_UPDATE = "portfolio_update"


@dataclass
class Event:
    trigger: TriggerType
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class EventBus:
    """Async event queue — triggers push, agent consumes."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self.events_processed: int = 0
        self.events_by_trigger: dict[str, int] = {t.value: 0 for t in TriggerType}

    async def emit(self, event: Event) -> None:
        await self.queue.put(event)
        self.events_by_trigger[event.trigger.value] += 1

    async def consume(self) -> Event:
        event = await self.queue.get()
        self.events_processed += 1
        return event

    @property
    def pending(self) -> int:
        return self.queue.qsize()

    def stats(self) -> dict:
        return {
            "processed": self.events_processed,
            "pending": self.pending,
            "by_trigger": dict(self.events_by_trigger),
        }
