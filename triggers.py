"""Event-driven triggers — independent async loops that emit events to the bus.

Each trigger polls a data source on its own interval and pushes Events
onto the shared EventBus when actionable conditions are detected.
"""

from __future__ import annotations

import asyncio
import json
import logging

from config import (
    CROSS_CHAIN_INTERVAL,
    CROSS_CHAIN_THRESHOLD,
    FUNDING_RATE_THRESHOLD,
    FUNDING_TRIGGER_INTERVAL,
    KOL_TRIGGER_INTERVAL,
    POLYMARKET_TRIGGER_INTERVAL,
    PORTFOLIO_TRIGGER_INTERVAL,
    TOKEN_DISCOVERY_INTERVAL,
)
from event_bus import Event, EventBus, TriggerType
from kol_tracker import detect_kol_signals
from mcp_client import BobaClient
from signals import detect_signals

logger = logging.getLogger(__name__)


def _backoff_delay(base_interval: float, consecutive_errors: int) -> float:
    """Exponential backoff: base_interval * 2^errors, capped at 10 minutes."""
    if consecutive_errors <= 0:
        return base_interval
    return min(base_interval * (2 ** consecutive_errors), 600)


async def polymarket_trigger(boba: BobaClient, bus: EventBus) -> None:
    """Polls Polymarket every 60s, emits event when >5% move detected."""
    errors = 0
    while True:
        try:
            signals = await detect_signals(boba)
            errors = 0  # reset on success
            for signal in signals:
                await bus.emit(Event(
                    trigger=TriggerType.POLYMARKET_MOVE,
                    data={"signal": signal},
                ))
        except Exception as e:
            errors += 1
            logger.warning("Polymarket trigger error (attempt %d): %s", errors, e)
        await asyncio.sleep(_backoff_delay(POLYMARKET_TRIGGER_INTERVAL, errors))


async def kol_trigger(boba: BobaClient, bus: EventBus) -> None:
    """Polls KOL swaps every 90s, emits event when whale trade >$10k found."""
    errors = 0
    while True:
        try:
            kol_signals = await detect_kol_signals(boba)
            errors = 0
            for ks in kol_signals:
                await bus.emit(Event(
                    trigger=TriggerType.KOL_WHALE_TRADE,
                    data={"kol_signal": ks},
                ))
        except Exception as e:
            errors += 1
            logger.warning("KOL trigger error (attempt %d): %s", errors, e)
        await asyncio.sleep(_backoff_delay(KOL_TRIGGER_INTERVAL, errors))


async def funding_trigger(boba: BobaClient, bus: EventBus) -> None:
    """Polls Hyperliquid funding rates every 120s, emits when rate deviates significantly."""
    errors = 0
    while True:
        try:
            raw = await boba.call_tool("hl_get_predicted_funding", {})
            # Parse response — look for assets where HL funding differs
            # from Binance/Bybit by more than FUNDING_RATE_THRESHOLD
            data = json.loads(raw) if isinstance(raw, str) else raw
            rates = (
                data
                if isinstance(data, list)
                else data.get("rates", data.get("assets", []))
            )
            for asset_rate in rates:
                # Extract HL rate and compare to Binance/Bybit
                hl_rate = float(
                    asset_rate.get("hl", asset_rate.get("funding", 0)) or 0
                )
                binance_rate = float(
                    asset_rate.get("binance", asset_rate.get("bin", 0)) or 0
                )
                diff = abs(hl_rate - binance_rate)
                if diff > FUNDING_RATE_THRESHOLD:
                    asset = asset_rate.get(
                        "name",
                        asset_rate.get("asset", asset_rate.get("coin", "")),
                    )
                    if asset:
                        await bus.emit(Event(
                            trigger=TriggerType.FUNDING_RATE_SPIKE,
                            data={
                                "asset": asset,
                                "hl_rate": hl_rate,
                                "binance_rate": binance_rate,
                                "diff": diff,
                            },
                        ))
            errors = 0
        except Exception as e:
            errors += 1
            logger.warning("Funding trigger error (attempt %d): %s", errors, e)
        await asyncio.sleep(_backoff_delay(FUNDING_TRIGGER_INTERVAL, errors))


async def token_discovery_trigger(boba: BobaClient, bus: EventBus) -> None:
    """Polls search_tokens every 180s, emits event for trending tokens."""
    while True:
        try:
            result = await boba.call_tool("search_tokens", {
                "sort_by": "change24",
                "sort_direction": "DESC",
                "price_change_24h": {"gte": 0.5},  # >50% 24h change
                "volume_24h": {"gte": 100000},      # >$100k volume
                "limit": 10,
            })
            data = json.loads(result) if isinstance(result, str) else result
            tokens = (
                data
                if isinstance(data, list)
                else data.get("tokens", data.get("results", []))
            )
            for token in tokens:
                price_change = float(
                    token.get("price_change_24h", token.get("change24", 0)) or 0
                )
                volume = float(
                    token.get("volume_24h", token.get("volume", 0)) or 0
                )
                if price_change > 0.5 and volume > 100000:
                    await bus.emit(Event(
                        trigger=TriggerType.TOKEN_DISCOVERY,
                        data={
                            "token_address": token.get("address", token.get("token_address", "")),
                            "chain": token.get("chain", token.get("chainId", "")),
                            "symbol": token.get("symbol", ""),
                            "price_change_24h": price_change,
                            "volume_24h": volume,
                            "market_cap": float(token.get("market_cap", token.get("marketCap", 0)) or 0),
                        },
                    ))
        except Exception as e:
            logger.warning("Token discovery trigger error: %s", e)

        # Also check launchpad tokens close to graduating
        try:
            brewing_raw = await boba.call_tool("get_brewing_tokens", {
                "table": "steeping",  # tokens close to graduating
                "sort_by": "graduationPercent",
                "sort_direction": "DESC",
                "limit": 10,
            })
            brewing_data = json.loads(brewing_raw) if isinstance(brewing_raw, str) else brewing_raw
            tokens = brewing_data if isinstance(brewing_data, list) else brewing_data.get("tokens", [])
            for token in tokens:
                grad_pct = float(token.get("graduationPercent", token.get("graduation_percent", 0)) or 0)
                if grad_pct > 80:  # Close to graduating
                    await bus.emit(Event(
                        trigger=TriggerType.TOKEN_DISCOVERY,
                        data={
                            "source": "launchpad",
                            "symbol": token.get("symbol", token.get("name", "")),
                            "graduation_percent": grad_pct,
                            "market_cap": token.get("marketCap", token.get("market_cap", 0)),
                        },
                    ))
        except Exception as e:
            logger.debug("Brewing tokens: %s", e)

        await asyncio.sleep(TOKEN_DISCOVERY_INTERVAL)


async def cross_chain_trigger(boba: BobaClient, bus: EventBus) -> None:
    """Compares token prices across chains every 300s, emits on >0.5% diff."""
    assets = [
        {
            "name": "ETH",
            "tokens": [
                ("native:1", "Ethereum"),
                ("native:8453", "Base"),
                ("native:42161", "Arbitrum"),
            ],
        },
    ]
    while True:
        try:
            for asset_def in assets:
                asset_name = asset_def["name"]
                token_ids = [t[0] for t in asset_def["tokens"]]
                chain_names = [t[1] for t in asset_def["tokens"]]

                result = await boba.call_tool("get_token_price", {
                    "tokens": token_ids,
                })
                data = json.loads(result) if isinstance(result, str) else result

                # Extract prices — handle both list and dict responses
                prices: list[float] = []
                if isinstance(data, list):
                    for item in data:
                        p = float(item.get("price", item.get("usdPrice", 0)) or 0)
                        prices.append(p)
                elif isinstance(data, dict):
                    for tid in token_ids:
                        entry = data.get(tid, data.get(tid.replace(":", "_"), {}))
                        if isinstance(entry, dict):
                            p = float(entry.get("price", entry.get("usdPrice", 0)) or 0)
                        else:
                            p = float(entry or 0)
                        prices.append(p)

                # Compare all pairs
                for i in range(len(prices)):
                    for j in range(i + 1, len(prices)):
                        if prices[i] <= 0 or prices[j] <= 0:
                            continue
                        avg = (prices[i] + prices[j]) / 2
                        diff_pct = abs(prices[i] - prices[j]) / avg
                        if diff_pct > CROSS_CHAIN_THRESHOLD:
                            await bus.emit(Event(
                                trigger=TriggerType.CROSS_CHAIN_OPPORTUNITY,
                                data={
                                    "asset": asset_name,
                                    "chain_a": chain_names[i],
                                    "chain_b": chain_names[j],
                                    "price_a": prices[i],
                                    "price_b": prices[j],
                                    "diff_pct": diff_pct,
                                },
                            ))
        except Exception as e:
            logger.warning("Cross-chain trigger error: %s", e)
        await asyncio.sleep(CROSS_CHAIN_INTERVAL)


async def portfolio_trigger(boba: BobaClient, bus: EventBus):
    """Poll Boba portfolio for real wallet state."""
    while True:
        try:
            raw = await boba.call_tool("get_portfolio", {"user_id": "me", "summary": True})
            data = json.loads(raw) if isinstance(raw, str) else raw
            await bus.emit(Event(
                trigger=TriggerType.PORTFOLIO_UPDATE,
                data={"portfolio": data},
            ))
        except Exception as e:
            logger.debug("Portfolio trigger: %s", e)
        await asyncio.sleep(PORTFOLIO_TRIGGER_INTERVAL)
