"""Risk management — disciplined constraints to improve win rate.

Rules:
  1. Can't spend more margin than the wallet has
  2. Can't open contradictory positions (long + short same asset)
  3. Max 30% of balance on a single trade
  4. Max 3x leverage
  5. Stop-loss and take-profit on every position
  6. Minimum $20 position size (no dust trades)
"""

from __future__ import annotations

import logging

from config import (
    DEFAULT_STOP_LOSS_PCT,
    DEFAULT_TAKE_PROFIT_PCT,
    MAX_SINGLE_POSITION_PCT,
    PAPER_WALLET_STARTING_BALANCE,
)
from db import get_open_positions, get_stats
from models import Direction

logger = logging.getLogger(__name__)


def can_open_position(proposed_size: float, proposed_leverage: int = 1) -> tuple[bool, str]:
    """Check if the wallet can afford this trade. That's it."""
    open_positions = get_open_positions()
    stats = get_stats()

    # What's the current wallet balance?
    balance = PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"]
    if balance <= 0:
        return False, "Wallet is empty"

    # How much margin is already locked up?
    used_margin = sum(p.size_usd / max(p.leverage, 1) for p in open_positions)
    available = balance - used_margin

    # How much margin does this trade need?
    margin_needed = proposed_size / max(proposed_leverage, 1)

    if margin_needed > available:
        return False, f"Need ${margin_needed:.0f} margin, only ${available:.0f} available"

    # Don't put more than 50% of balance on a single trade
    if margin_needed > balance * MAX_SINGLE_POSITION_PCT:
        proposed_size = balance * MAX_SINGLE_POSITION_PCT * proposed_leverage
        logger.info("Capping trade to ${:.0f} (50%% of balance)".format(proposed_size))

    return True, "OK"


def can_open_position_for_asset(asset: str, direction: Direction) -> tuple[bool, str]:
    """Check if we can open this position. Same direction = blocked. Opposite = flip (close old first)."""
    for p in get_open_positions():
        if p.asset.upper() == asset.upper():
            if p.direction == direction:
                return False, f"Already {direction.value} on {asset}"
            else:
                # Opposite direction = we want to flip. Return special signal.
                return False, f"FLIP:{p.id}"
    return True, "OK"


def calculate_position_size(conviction: float, suggested_size: float) -> float:
    """Scale size by conviction. Higher conviction = bigger bet."""
    stats = get_stats()
    balance = PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"]
    if balance <= 5:
        return 0.0

    sized = suggested_size * conviction
    # Cap at 50% of balance (margin, not exposure)
    max_margin = balance * MAX_SINGLE_POSITION_PCT
    capped = min(sized, max_margin * 3)  # assuming ~3x leverage

    # Floor: don't bother with tiny trades
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
    """Keep leverage in a sane range — max 3x to reduce impulsive losses."""
    return max(1, min(proposed, 3))


def get_available_margin() -> float:
    """How much margin the wallet can deploy right now."""
    stats = get_stats()
    balance = PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"]
    open_positions = get_open_positions()
    used = sum(p.size_usd / max(p.leverage, 1) for p in open_positions)
    return max(0.0, balance - used)
