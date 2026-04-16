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
    FUNDING_EXTREME_THRESHOLD,
    FUNDING_RATE_THRESHOLD,
    FUNDING_TRIGGER_INTERVAL,
    HL_WHALE_FLOW_IMBALANCE_RATIO,
    HL_WHALE_LOOKBACK_TRADES,
    HL_WHALE_MIN_FILL_USD,
    HL_WHALE_MIN_TOTAL_USD,
    HL_WHALE_TRIGGER_INTERVAL,
    KOL_TRIGGER_INTERVAL,
    POLYMARKET_TRIGGER_INTERVAL,
    PORTFOLIO_TRIGGER_INTERVAL,
    TOKEN_DISCOVERY_INTERVAL,
    TRADABLE_ASSETS,
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
    """Poll predicted funding rates and emit on EXTREMES or cross-venue divergence.

    Two trigger conditions (v2):
      1. Extreme: |HL rate| > FUNDING_EXTREME_THRESHOLD per 8h (crowded longs/shorts)
         → contrarian signal (fade the crowd).
      2. Divergence: |HL − Binance| > FUNDING_RATE_THRESHOLD (legacy arb edge).

    Both emit FUNDING_RATE_SPIKE events with the same shape; the agent's
    scoring layer uses the ``hl_rate`` to derive a directional score.
    """
    errors = 0
    while True:
        try:
            raw = await boba.call_tool("hl_get_predicted_funding", {})
            data = json.loads(raw) if isinstance(raw, str) else raw
            rates = (
                data
                if isinstance(data, list)
                else data.get("rates", data.get("assets", []))
            )
            for asset_rate in rates:
                asset = asset_rate.get(
                    "name",
                    asset_rate.get("asset", asset_rate.get("coin", "")),
                )
                if not asset:
                    continue
                asset_u = asset.upper()
                # Only emit for assets we can actually trade
                if asset_u not in TRADABLE_ASSETS:
                    continue

                hl_rate = float(
                    asset_rate.get("hl", asset_rate.get("funding", 0)) or 0
                )
                binance_rate = float(
                    asset_rate.get("binance", asset_rate.get("bin", 0)) or 0
                )
                diff = abs(hl_rate - binance_rate)

                is_extreme = abs(hl_rate) > FUNDING_EXTREME_THRESHOLD
                is_divergent = diff > FUNDING_RATE_THRESHOLD

                if is_extreme or is_divergent:
                    await bus.emit(Event(
                        trigger=TriggerType.FUNDING_RATE_SPIKE,
                        data={
                            "asset": asset_u,
                            "hl_rate": hl_rate,
                            "binance_rate": binance_rate,
                            "diff": diff,
                            "extreme": is_extreme,
                            "divergent": is_divergent,
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


def _parse_oi(val) -> float:
    """Parse an OI string like "2.02B", "38.4M", "2.2M", "45.0K" into a float."""
    if val is None:
        return 0.0
    s = str(val).strip().upper().replace(",", "").replace("$", "")
    mult = 1.0
    if s.endswith("B"):
        mult = 1e9; s = s[:-1]
    elif s.endswith("M"):
        mult = 1e6; s = s[:-1]
    elif s.endswith("K"):
        mult = 1e3; s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


async def hl_whale_trigger(boba: BobaClient, bus: EventBus) -> None:
    """Emit HL_WHALE_FLOW events from Open Interest deltas on Hyperliquid.

    Hyperliquid doesn't expose a trade-tape MCP tool (only candles + funding),
    so we infer whale positioning from OI changes. Every HL_WHALE_TRIGGER_INTERVAL
    we snapshot OI per asset via hl_get_markets, compare against the previous
    snapshot (kept in memory), and interpret:

      OI ↑  + price ↑  →  longs opening   →  bullish
      OI ↑  + price ↓  →  shorts opening  →  bearish
      OI ↓  + price ↑  →  shorts covering →  bullish (short squeeze)
      OI ↓  + price ↓  →  longs closing   →  bearish (capitulation)

    Only emits when |ΔOI| >= 5% over the window — i.e. meaningful positioning
    change, not noise. Price is compared at mark. This is a stronger signal
    than trade-tape churn because OI reflects *net new commitment*.
    """
    whale_assets = ["BTC", "ETH", "SOL", "DOGE", "AVAX", "LINK"]
    # Per-asset rolling window: {asset: [(timestamp, oi_usd, mark_price), ...]}
    # We keep ~6 snapshots (~18 min at 3-min interval) and compare current to
    # oldest-in-window. This lets delta accumulate over time — a 2% drift over
    # 18 min is far more common (and actionable) than a 5% spike in 3 min.
    oi_window: dict[str, list[tuple[float, float, float]]] = {}
    WINDOW_SIZE = 6                 # ~18 minutes of snapshots
    min_oi_change_pct = 0.02        # 2% OI shift over the full window ⇒ meaningful
    poll_count = 0
    errors = 0

    while True:
        try:
            import time as _time
            now = _time.time()
            poll_count += 1
            emitted = 0
            for asset in whale_assets:
                try:
                    raw = await boba.call_tool("hl_get_markets", {"search": asset, "limit": 1})
                    data = json.loads(raw) if isinstance(raw, str) else raw
                    assets = data.get("assets", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    if not assets:
                        continue
                    rec = assets[0]
                    if str(rec.get("name", "")).upper() != asset:
                        continue

                    mark = float(str(rec.get("mark", 0)).replace(",", ""))
                    oi_units = _parse_oi(rec.get("oi"))
                    oi_usd = oi_units * mark  # OI in USD terms

                    # Update rolling window (keep last WINDOW_SIZE entries)
                    win = oi_window.setdefault(asset, [])
                    win.append((now, oi_usd, mark))
                    if len(win) > WINDOW_SIZE:
                        win.pop(0)
                    if len(win) < 2:
                        continue  # need at least two snapshots to compute delta

                    # Compare current to OLDEST snapshot in the window
                    prev_ts, prev_oi, prev_mark = win[0]
                    if prev_oi <= 0 or prev_mark <= 0 or mark <= 0:
                        continue
                    dt_min = (now - prev_ts) / 60.0

                    oi_change = (oi_usd - prev_oi) / prev_oi
                    price_change = (mark - prev_mark) / prev_mark

                    if abs(oi_change) < min_oi_change_pct:
                        continue  # no meaningful positioning change

                    # Interpret direction
                    oi_up = oi_change > 0
                    price_up = price_change > 0
                    if oi_up and price_up:
                        direction = "long"; interp = "longs opening"
                    elif oi_up and not price_up:
                        direction = "short"; interp = "shorts opening"
                    elif (not oi_up) and price_up:
                        direction = "long"; interp = "shorts covering"
                    else:
                        direction = "short"; interp = "longs closing"

                    logger.info(
                        "HL whale flow %s: %s (%s) ΔOI=%+.1f%% Δpx=%+.2f%% "
                        "(OI $%.1fM → $%.1fM, %.1fm window)",
                        asset, direction, interp, oi_change * 100, price_change * 100,
                        prev_oi / 1e6, oi_usd / 1e6, dt_min,
                    )
                    await bus.emit(Event(
                        trigger=TriggerType.HL_WHALE_FLOW,
                        data={
                            "asset": asset,
                            "direction": direction,
                            "oi_change": oi_change,
                            "price_change": price_change,
                            "oi_usd": oi_usd,
                            "prev_oi_usd": prev_oi,
                            "mark": mark,
                            "interpretation": interp,
                            # Use oi_change magnitude as a "ratio-like" intensity
                            "ratio": 1.0 + abs(oi_change) * 10,  # 5% OI ⇒ 1.5, 10% ⇒ 2.0
                            "buy_usd": oi_usd if direction == "long" else 0,
                            "sell_usd": oi_usd if direction == "short" else 0,
                        },
                    ))
                    emitted += 1
                except Exception as e:
                    logger.debug("HL OI poll for %s failed: %s", asset, e)

            # Heartbeat: confirm trigger is alive even when no signal fires
            if poll_count == 1 or poll_count % 5 == 0 or emitted > 0:
                window_sizes = {a: len(v) for a, v in oi_window.items()}
                logger.info(
                    "HL whale poll #%d complete: emitted=%d, window_sizes=%s",
                    poll_count, emitted, window_sizes,
                )
            errors = 0
        except Exception as e:
            errors += 1
            logger.warning("HL whale trigger error (attempt %d): %s", errors, e)
        await asyncio.sleep(_backoff_delay(HL_WHALE_TRIGGER_INTERVAL, errors))


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
