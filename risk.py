"""Risk management — keep enough cash to always be able to trade.

Rules:
  1. Always keep 20% of balance as cash reserve (never go all-in)
  2. Max 25% of balance per trade (so we can have 3-4 positions)
  3. Can't open contradictory positions (long + short same asset)
  4. Max 3x leverage
  5. Stop-loss and take-profit on every position
"""

from __future__ import annotations

import logging

from config import (
    DEFAULT_STOP_LOSS_PCT,
    DEFAULT_TAKE_PROFIT_PCT,
    PAPER_WALLET_STARTING_BALANCE,
    MAX_CONCURRENT_POSITIONS,
)
from db import get_open_positions, get_stats
from models import Direction

logger = logging.getLogger(__name__)

CASH_RESERVE_PCT = 0.20    # always keep 20% of balance free
MAX_PER_TRADE_PCT = 0.25   # max 25% of balance on one trade


def can_open_position(proposed_size: float, proposed_leverage: int = 1) -> tuple[bool, str]:
    """Check if we have margin AND aren't over-allocated."""
    open_positions = get_open_positions()
    stats = get_stats()

    balance = PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"]
    if balance <= 5:
        return False, "Wallet is empty"

    # Enforce max concurrent positions
    if len(open_positions) >= MAX_CONCURRENT_POSITIONS:
        return False, f"Already at max positions ({MAX_CONCURRENT_POSITIONS})"

    # Calculate available margin (with cash reserve)
    used_margin = sum(p.size_usd / max(p.leverage, 1) for p in open_positions)
    reserved = balance * CASH_RESERVE_PCT
    available = balance - used_margin - reserved

    margin_needed = proposed_size / max(proposed_leverage, 1)

    if margin_needed > available:
        return False, f"Need ${margin_needed:.0f} margin, only ${available:.0f} available (${reserved:.0f} reserved)"

    return True, "OK"


def can_open_position_for_asset(asset: str, direction: Direction) -> tuple[bool, str]:
    """Same direction = blocked. Opposite = flip (close old first)."""
    for p in get_open_positions():
        if p.asset.upper() == asset.upper():
            if p.direction == direction:
                return False, f"Already {direction.value} on {asset}"
            else:
                return False, f"FLIP:{p.id}"
    return True, "OK"


def calculate_position_size(conviction: float, suggested_size: float) -> float:
    """Size based on conviction, capped to keep cash reserve."""
    stats = get_stats()
    balance = PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"]
    if balance <= 5:
        return 0.0

    open_positions = get_open_positions()
    used_margin = sum(p.size_usd / max(p.leverage, 1) for p in open_positions)
    reserved = balance * CASH_RESERVE_PCT
    available = balance - used_margin - reserved

    # Scale by conviction
    sized = suggested_size * conviction

    # Cap at 25% of total balance (margin, before leverage)
    max_margin = balance * MAX_PER_TRADE_PCT
    # Apply leverage (assume 3x) to get exposure
    capped = min(sized, max_margin * 3)

    # Also cap by what's actually available
    margin_for_capped = capped / 3  # assuming 3x leverage
    if margin_for_capped > available:
        capped = available * 3

    if capped < 20:
        return 0.0
    return round(capped, 2)


def compute_stop_take(
    entry_price: float,
    direction: Direction,
    stop_pct: float = DEFAULT_STOP_LOSS_PCT,
    tp_pct: float = DEFAULT_TAKE_PROFIT_PCT,
) -> tuple[float, float]:
    """Calculate stop-loss and take-profit prices."""
    if direction == Direction.LONG:
        stop_loss = entry_price * (1 - stop_pct)
        take_profit = entry_price * (1 + tp_pct)
    else:
        stop_loss = entry_price * (1 + stop_pct)
        take_profit = entry_price * (1 - tp_pct)

    return round(stop_loss, 2), round(take_profit, 2)


def clamp_leverage(proposed: int) -> int:
    """Max 3x leverage."""
    return max(1, min(proposed, 3))


def get_available_margin() -> float:
    """How much margin the wallet can deploy right now (after reserve)."""
    stats = get_stats()
    balance = PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"]
    open_positions = get_open_positions()
    used = sum(p.size_usd / max(p.leverage, 1) for p in open_positions)
    reserved = balance * CASH_RESERVE_PCT
    return max(0.0, balance - used - reserved)
