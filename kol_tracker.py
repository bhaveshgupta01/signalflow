"""Smart-money wallet tracking (v2.2).

Replaces the old `get_kol_swaps` pipeline that was frozen on a curated
10-wallet Solana memecoin list and collapsed every trade to "SOL". The new
flow:

  Discovery  — `search_wallets` periodically pulls the top-PnL wallets on
               each chain we care about (Solana, Base, Ethereum), filtered
               to real traders (min win rate, min profit, low bot score).
  Polling    — `get_wallet_swaps` per discovered wallet every cycle.
  Extraction — preserves the REAL traded asset (not "SOL" for everything),
               respects BUY/SELL direction, only emits signals for assets
               we can actually trade on Hyperliquid.

Writes to the same `kol_signals` table as before (shape-compatible).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from config import (
    KOL_DEDUP_MINUTES,
    KOL_MIN_TRADE_USD,
    KOL_POLL_ENABLED,
    TRADABLE_ASSETS,
)
from db import get_recent_kol_signals, save_kol_signal
from mcp_client import BobaClient
from models import Direction, KolSignal

logger = logging.getLogger(__name__)


# Chain IDs we discover smart money on. Each chain is queried independently
# so a top ETH trader's trades are scored separately from a top SOL trader's.
_SMART_MONEY_CHAINS = [
    (1399811149, "Solana"),
    (1, "Ethereum"),
    (8453, "Base"),
]

# How long we cache a discovered top-wallet list before re-running search_wallets.
_DISCOVERY_REFRESH_MINUTES = 60

# In-memory wallet cache: {chain_id: (refreshed_at, [wallet_addr, ...])}
_wallet_cache: dict[int, tuple[datetime, list[str]]] = {}

# Ignore these — they're quote assets, stablecoins, or wrapping layers, not
# directional bets on a coin.
_UNTRADABLE_SYMBOLS = {
    "USDC", "USDT", "USD", "DAI", "BUSD", "FDUSD", "USDE",
    "WETH", "WBTC", "WSOL",
}


# ── Public API ───────────────────────────────────────────────────────────────

async def detect_kol_signals(boba: BobaClient) -> list[KolSignal]:
    """Poll smart-money wallets and emit signals for trades we can mirror."""
    if not KOL_POLL_ENABLED:
        return []

    signals: list[KolSignal] = []
    recent_existing = get_recent_kol_signals(minutes=KOL_DEDUP_MINUTES)
    seen_keys = {(k.wallet_address, k.asset, k.direction.value) for k in recent_existing}

    # Step 1: make sure we have a fresh wallet list per chain
    wallets_by_chain = await _refresh_wallet_cache(boba)
    total_wallets = sum(len(w) for w in wallets_by_chain.values())
    if total_wallets == 0:
        logger.info("Smart money: no wallets discovered across %d chains", len(_SMART_MONEY_CHAINS))
        return []

    # Step 2: pull recent swaps per wallet (bounded concurrency)
    all_swaps: list[tuple[str, int, dict]] = []  # (wallet, chain_id, swap_dict)
    for chain_id, wallets in wallets_by_chain.items():
        # Poll wallets sequentially per chain to avoid rate-limiting.
        for wallet in wallets:
            try:
                raw = await boba.call_tool(
                    "get_wallet_swaps",
                    {"wallet_address": wallet, "chain_id": chain_id, "limit": 10},
                )
                swaps = _parse_swaps(raw)
                for s in swaps:
                    all_swaps.append((wallet, chain_id, s))
            except Exception as e:
                logger.debug("get_wallet_swaps failed for %s: %s", wallet[:12], e)

    logger.info(
        "Smart money poll: %d wallets across %d chains → %d raw swaps",
        total_wallets, len(wallets_by_chain), len(all_swaps),
    )

    # Step 3: extract tradable signals
    for wallet, chain_id, swap in all_swaps:
        asset = _extract_tradable_asset(swap)
        if not asset:
            continue
        direction = _infer_direction(swap)
        size_usd = _extract_size(swap)

        if size_usd < KOL_MIN_TRADE_USD:
            continue

        key = (wallet, asset, direction.value)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        kol_name = _display_name(wallet, swap)
        signal = KolSignal(
            kol_name=kol_name,
            wallet_address=wallet,
            asset=asset,
            direction=direction,
            trade_size_usd=size_usd,
            detected_at=datetime.utcnow(),
        )
        signal = save_kol_signal(signal)
        signals.append(signal)
        logger.info(
            "Smart money signal: %s %s %s $%.0f (chain=%s, wallet=%s...)",
            kol_name, direction.value, asset, size_usd, chain_id, wallet[:8],
        )

    return signals


def check_kol_alignment(asset: str, direction: Direction, minutes: int = 60) -> list[KolSignal]:
    """Check if any recent KOL/smart-money signals align with a proposed trade."""
    from db import get_kol_signals_for_asset
    kol_signals = get_kol_signals_for_asset(asset, minutes=minutes)
    return [k for k in kol_signals if k.direction == direction]


# ── Wallet discovery ─────────────────────────────────────────────────────────

async def _refresh_wallet_cache(boba: BobaClient) -> dict[int, list[str]]:
    """Return {chain_id: [wallet, ...]} refreshing the cache if stale."""
    now = datetime.utcnow()
    out: dict[int, list[str]] = {}

    for chain_id, chain_name in _SMART_MONEY_CHAINS:
        cached = _wallet_cache.get(chain_id)
        if cached:
            refreshed_at, wallets = cached
            age_min = (now - refreshed_at).total_seconds() / 60
            if age_min < _DISCOVERY_REFRESH_MINUTES:
                out[chain_id] = wallets
                continue

        try:
            raw = await boba.call_tool("search_wallets", {
                "chain": chain_id,
                "period": "1w",
                "min_swaps": 20,
                "min_win_rate": 55,
                "min_profit_usd": 5000,
                "max_bot_score": 50,
                "sort_by": "realizedProfitUsd",
                "sort_dir": "DESC",
                "limit": 10,
            })
            wallets = _parse_wallet_addresses(raw)
        except Exception as e:
            logger.warning("search_wallets (%s) failed: %s", chain_name, e)
            wallets = []

        _wallet_cache[chain_id] = (now, wallets)
        out[chain_id] = wallets
        logger.info("Smart money discovery: %s → %d wallets", chain_name, len(wallets))

    return out


def _parse_wallet_addresses(raw: str) -> list[str]:
    """Extract wallet addresses from search_wallets response."""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []

    items = data if isinstance(data, list) else data.get("wallets", data.get("results", data.get("data", [])))
    addrs: list[str] = []
    for item in items:
        if isinstance(item, str):
            addrs.append(item)
        elif isinstance(item, dict):
            a = (item.get("wallet_address") or item.get("address")
                 or item.get("wallet") or item.get("walletAddress"))
            if a:
                addrs.append(a)
    return addrs


# ── Swap parsing ─────────────────────────────────────────────────────────────

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


def _extract_tradable_asset(swap: dict) -> str:
    """Return the non-quote asset from this swap, if it's one we can trade.

    Unlike the old _extract_asset, this:
      - Returns "" for stable/wrapped-side-only trades (no signal).
      - PREFERS the non-stable, non-native side (the actual bet).
      - Maps wrapped assets to their underlying (WETH→ETH, WBTC→BTC).
      - Does NOT fall back to native chain asset — we want the bet, not SOL.
    """
    bought = (swap.get("bought") or {}).get("sym", "").upper()
    sold = (swap.get("sold") or {}).get("sym", "").upper()
    if not bought and not sold:
        # Try legacy flat shape
        bought = (swap.get("buy_symbol") or swap.get("token_bought") or "").upper()
        sold = (swap.get("sell_symbol") or swap.get("token_sold") or "").upper()

    # Determine BUY vs SELL perspective
    swap_type = str(swap.get("type") or swap.get("side") or "").upper()
    is_buy = "BUY" in swap_type
    is_sell = "SELL" in swap_type

    # The "bet" asset is bought on a BUY, sold on a SELL
    bet = bought if is_buy else sold if is_sell else (bought or sold)

    if bet in _UNTRADABLE_SYMBOLS:
        # Hop to the other side if the bet side was a stable/wrapper
        alt = sold if is_buy else bought
        if alt and alt not in _UNTRADABLE_SYMBOLS:
            bet = alt

    # Normalise wrapped versions
    wrapped_map = {"WETH": "ETH", "WBTC": "BTC", "WSOL": "SOL"}
    bet = wrapped_map.get(bet, bet)

    if bet in TRADABLE_ASSETS:
        return bet
    return ""


def _extract_size(swap: dict) -> float:
    """Extract trade size in USD from several possible field names."""
    usd = swap.get("usd")
    if usd is not None:
        try:
            return abs(float(str(usd).replace(",", "").replace("$", "")))
        except (ValueError, TypeError):
            pass
    for key in ("usd_value", "valueUsd", "amountUsd", "usdAmount", "volume", "size"):
        val = swap.get(key)
        if val is not None:
            try:
                return abs(float(str(val).replace(",", "").replace("$", "")))
            except (ValueError, TypeError):
                continue
    return 0.0


def _infer_direction(swap: dict) -> Direction:
    """BUY → long on the bought asset; SELL → short on the sold asset."""
    swap_type = str(swap.get("type") or swap.get("side") or swap.get("action") or "").upper()
    if "BUY" in swap_type:
        return Direction.LONG
    if "SELL" in swap_type:
        return Direction.SHORT
    if swap.get("bought") and not swap.get("sold"):
        return Direction.LONG
    if swap.get("sold") and not swap.get("bought"):
        return Direction.SHORT
    return Direction.LONG


def _display_name(wallet: str, swap: dict) -> str:
    """Short display name for logs — prefer the wallet label, else truncated addr."""
    kol = swap.get("kol") or {}
    name = kol.get("name") or swap.get("name") or swap.get("kol_name")
    if name:
        return name
    # Truncated wallet address for display
    return f"{wallet[:6]}…{wallet[-4:]}" if len(wallet) > 12 else wallet
