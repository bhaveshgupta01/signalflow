"""KOL (Key Opinion Leader) wallet tracking — whale signal detection.

Monitors KOL wallets via Boba's tracking tools. When a whale makes a
significant trade, it becomes an additional signal source that can boost
conviction when aligned with Polymarket signals.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from config import KOL_MIN_TRADE_USD, KOL_DEDUP_MINUTES, KOL_POLL_ENABLED
from db import get_recent_kol_signals, save_kol_signal
from mcp_client import BobaClient
from models import Direction, KolSignal

logger = logging.getLogger(__name__)


async def detect_kol_signals(boba: BobaClient) -> list[KolSignal]:
    """Poll KOL wallets via Boba and return significant new trades."""
    if not KOL_POLL_ENABLED:
        return []

    signals: list[KolSignal] = []
    recent_existing = get_recent_kol_signals(minutes=KOL_DEDUP_MINUTES)
    seen_keys = {(k.wallet_address, k.asset, k.direction.value) for k in recent_existing}

    # Step 1: Get recent KOL swap activity
    try:
        raw = await boba.call_tool("get_kol_swaps", {"limit": 30})
        swaps = _parse_swaps(raw)
    except Exception:
        logger.debug("Could not fetch KOL swaps")
        return []

    for swap in swaps:
        # Boba format nests KOL info: {"kol": {"name": "...", "wallet": "..."}}
        kol_info = swap.get("kol", {})
        kol_name = kol_info.get("name", swap.get("name", swap.get("kol_name", "Unknown")))
        wallet = swap.get("wallet", kol_info.get("wallet", swap.get("address", "")))
        asset = _extract_asset(swap)
        size_usd = _extract_size(swap)
        direction = _infer_direction(swap)

        if not asset or not wallet:
            continue

        # Filter: only significant trades
        if size_usd < KOL_MIN_TRADE_USD:
            continue

        # Dedup
        key = (wallet, asset.upper(), direction.value)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        signal = KolSignal(
            kol_name=kol_name,
            wallet_address=wallet,
            asset=asset.upper(),
            direction=direction,
            trade_size_usd=size_usd,
            detected_at=datetime.utcnow(),
        )
        signal = save_kol_signal(signal)
        signals.append(signal)
        logger.info(
            "KOL signal: %s %s %s $%.0f",
            kol_name, direction.value, asset, size_usd,
        )

    return signals


def check_kol_alignment(asset: str, direction: Direction, minutes: int = 60) -> list[KolSignal]:
    """Check if any recent KOL signals align with a proposed trade."""
    from db import get_kol_signals_for_asset
    kol_signals = get_kol_signals_for_asset(asset, minutes=minutes)
    return [k for k in kol_signals if k.direction == direction]


def _parse_swaps(raw: str) -> list[dict]:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("swaps", data.get("trades", data.get("results", [data])))
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _extract_asset(swap: dict) -> str:
    """Extract the traded asset symbol from a swap record.

    Boba KOL swaps come from DEX trades (mostly Solana memecoins).
    We extract the token being bought/sold and map to Hyperliquid-tradable assets.
    """
    # Boba format: swap has "bought" and "sold" dicts with "sym" field
    bought_sym = swap.get("bought", {}).get("sym", "").upper()
    sold_sym = swap.get("sold", {}).get("sym", "").upper()

    stables = {"USDC", "USDT", "USD", "DAI", "BUSD"}

    # The interesting asset is the non-stable, non-native one
    # If buying SOL with USDC -> asset is SOL
    # If selling MEME for SOL -> asset is SOL (since memecoins aren't on Hyperliquid)
    hl_tradable = {"BTC", "ETH", "SOL", "DOGE", "AVAX", "ARB", "MATIC", "LINK",
                   "OP", "SUI", "APT", "SEI", "TIA", "JUP", "WIF", "PEPE", "BONK",
                   "INJ", "NEAR", "FTM", "ATOM", "DOT", "ADA", "XRP", "BNB", "LTC"}

    # Check if either side is a Hyperliquid-tradable asset
    for sym in [bought_sym, sold_sym]:
        if sym in hl_tradable:
            return sym

    # Fallback: legacy format
    for key in ["token_symbol", "symbol", "token", "asset"]:
        val = swap.get(key, "").upper()
        if val and val in hl_tradable:
            return val

    # If it's a SOL memecoin trade, map to SOL (the chain's native asset)
    chain = swap.get("chain", 0)
    if chain == 1399811149 or bought_sym == "SOL" or sold_sym == "SOL":
        return "SOL"

    return ""


def _extract_size(swap: dict) -> float:
    """Extract trade size in USD.

    Boba format has top-level "usd" field with the trade value.
    """
    # Boba's primary format: top-level "usd" field
    usd = swap.get("usd")
    if usd is not None:
        try:
            return abs(float(str(usd).replace(",", "").replace("$", "")))
        except (ValueError, TypeError):
            pass

    # Fallback fields
    for key in ["usd_value", "valueUsd", "amountUsd", "usdAmount", "volume", "size"]:
        val = swap.get(key)
        if val is not None:
            try:
                return abs(float(str(val).replace(",", "").replace("$", "")))
            except (ValueError, TypeError):
                continue
    return 0.0


def _infer_direction(swap: dict) -> Direction:
    """Infer trade direction from swap data.

    Boba format: type is "BUY_WITH_NATIVE" or "SELL_FOR_NATIVE"
    BUY_WITH_NATIVE = selling SOL to buy a token = bullish on the token
    SELL_FOR_NATIVE = selling a token for SOL = bearish on the token (bullish SOL)
    """
    swap_type = str(swap.get("type", swap.get("side", swap.get("action", "")))).upper()

    if "BUY" in swap_type:
        # They're buying a token with SOL/native — bullish on the ecosystem
        return Direction.LONG
    if "SELL" in swap_type:
        # They're selling a token for SOL/native — could be taking profit
        # but they're accumulating SOL, so bullish on SOL
        return Direction.LONG  # selling memecoins = accumulating SOL = bullish

    # Fallback
    side = swap_type.lower()
    if side in ("buy", "long", "bid"):
        return Direction.LONG
    return Direction.SHORT
