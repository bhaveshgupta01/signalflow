"""Signal detection — scans Polymarket for crypto-related price moves.

This module is LLM-free. It uses pure Python math to filter markets,
so only significant moves get sent to Gemini for analysis.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from config import (
    MARKET_CATEGORIES,
    MIN_SIGNAL_PRICE_CHANGE,
    SIGNAL_DEDUP_MINUTES,
)
from db import get_signals_for_market, save_signal
from mcp_client import BobaClient
from models import Signal

logger = logging.getLogger(__name__)


async def detect_signals(boba: BobaClient) -> list[Signal]:
    """Poll Polymarket via Boba and return newly detected signals."""
    signals: list[Signal] = []
    seen_conditions: set[str] = set()  # dedup within a single scan

    for category in MARKET_CATEGORIES:
        try:
            raw = await boba.call_tool(
                "pm_search_markets",
                {"q": category, "limit": 10},
            )
            events = _parse_events(raw)
        except Exception:
            logger.exception("Failed to fetch markets for category=%s", category)
            continue

        for event in events:
            title = event.get("title", "")
            markets = event.get("markets", [])

            for mkt in markets:
                condition_id = mkt.get("conditionId", "")
                question = mkt.get("question", title)
                if not condition_id or condition_id in seen_conditions:
                    continue
                seen_conditions.add(condition_id)

                # Extract Yes token price and token ID
                tokens = mkt.get("tokens", [])
                yes_price = 0.0
                yes_token_id = ""
                for tok in tokens:
                    if tok.get("outcome") == "Yes":
                        yes_price = float(tok.get("price", 0))
                        yes_token_id = tok.get("tokenId", "")
                        break

                if yes_price <= 0 or not yes_token_id:
                    continue

                # Fetch price history using token ID (more reliable)
                price_change = await _get_price_change(boba, yes_token_id)

                # Filter: only keep significant moves
                if abs(price_change) < MIN_SIGNAL_PRICE_CHANGE:
                    continue

                # Skip dead markets (price near 0 or 1 = already resolved)
                if yes_price < 0.02 or yes_price > 0.98:
                    continue

                # De-duplicate: skip if we already signalled this market recently
                recent = get_signals_for_market(condition_id, minutes=SIGNAL_DEDUP_MINUTES)
                if recent:
                    logger.debug("Skipping duplicate signal for %s", condition_id[:16])
                    continue

                signal = Signal(
                    market_id=condition_id,
                    market_question=question,
                    current_price=yes_price,
                    price_change_pct=price_change,
                    timeframe_minutes=SIGNAL_DEDUP_MINUTES,
                    category=category,
                    detected_at=datetime.utcnow(),
                )
                signal = save_signal(signal)
                signals.append(signal)
                logger.info(
                    "Signal: %s | change=%.1f%% | price=%.3f",
                    question[:60], price_change * 100, yes_price,
                )

    return signals


async def _get_price_change(boba: BobaClient, token_id: str) -> float:
    """Fetch 1-day price history and compute the percentage change."""
    try:
        raw = await boba.call_tool(
            "pm_get_price_history",
            {"market": token_id, "interval": "1d", "fidelity": 24},
        )
        data = json.loads(raw) if isinstance(raw, str) else raw
        # Response is a list of {"t": timestamp, "p": price}
        history = data if isinstance(data, list) else data.get("history", [])

        if isinstance(history, list) and len(history) >= 2:
            old_price = float(history[0].get("p", 0))
            new_price = float(history[-1].get("p", 0))
            if old_price > 0:
                return (new_price - old_price) / old_price
    except Exception:
        logger.debug("Could not fetch price history for token %s", token_id[:20])
    return 0.0


def _parse_events(raw: str) -> list[dict]:
    """Parse the pm_search_markets response into a list of events."""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, dict):
            return data.get("events", [data])
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return []
