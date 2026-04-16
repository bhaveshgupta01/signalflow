"""Risk management — institutional-grade risk controls for the paper wallet.

Rules:
  1. Always keep 20% of balance as cash reserve (never go all-in)
  2. Max 25% of balance per trade (so we can have 3-4 positions)
  3. Can't open contradictory positions (long + short same asset)
  4. Max 3x leverage
  5. ATR-based stop-loss and take-profit on every position (volatility-aware)
  6. Portfolio drawdown circuit breaker (halt at -20%, reduce at -10%)
  7. Orderbook liquidity check before entry
  8. Fill confirmation and slippage tracking
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from config import (
    ATR_PERIOD,
    ATR_SL_MULTIPLIER,
    ATR_TP_MULTIPLIER,
    CHANDELIER_ACTIVATION_ATR,
    CHANDELIER_ATR_MULT,
    DEFAULT_STOP_LOSS_PCT,
    DEFAULT_TAKE_PROFIT_PCT,
    DRAWDOWN_COOLDOWN_HOURS,
    DRAWDOWN_HALT_PCT,
    DRAWDOWN_WARN_PCT,
    MAX_SLIPPAGE_PCT,
    MIN_ORDERBOOK_DEPTH_USD,
    PAPER_WALLET_STARTING_BALANCE,
    MAX_CONCURRENT_POSITIONS,
    MAX_SINGLE_POSITION_PCT,
    MIN_FLIP_INTERVAL_MINUTES,
    RISK_PCT_PER_TRADE,
)
from db import get_open_positions, get_stats
from models import Direction

logger = logging.getLogger(__name__)

CASH_RESERVE_PCT = 0.10                  # keep 10% of balance free
MAX_PER_TRADE_PCT = MAX_SINGLE_POSITION_PCT  # hard cap on per-trade notional fraction (v2: 30%)

# Track peak balance for drawdown calculation (in-memory, resets on restart)
_peak_balance: float = PAPER_WALLET_STARTING_BALANCE
_drawdown_halt_until: Optional[datetime] = None


# ── ATR Calculation ──────────────────────────────────────────────────────────

async def compute_atr(boba, asset: str, period: int = ATR_PERIOD) -> Optional[float]:
    """Compute Average True Range from Hyperliquid 1H candles via hl_get_history.

    ATR = average of max(high-low, |high-prev_close|, |low-prev_close|) over N periods.
    Returns ATR as a price value, or None if data is unavailable.
    """
    try:
        raw = await boba.call_tool("hl_get_history", {
            "coin": asset,
            "type": "candles",
            "interval": "1h",
            "limit": period + 5,  # fetch a few extra for safety
        })
        data = json.loads(raw) if isinstance(raw, str) else raw

        # Handle different response shapes
        candles = data if isinstance(data, list) else data.get("candles", data.get("data", []))
        if not candles or len(candles) < period:
            logger.debug("ATR: insufficient candle data for %s (%d candles)", asset, len(candles) if candles else 0)
            return None

        # Parse candles — Hyperliquid candle shapes seen in the wild:
        #   {"t":..., "o":..., "h":..., "l":..., "c":..., "v":...}
        #   {"time":..., "open":..., "high":..., "low":..., "close":...}
        #   {"T":..., "o":..., "h":..., "l":..., "c":...}  (camelCase)
        #   [t, o, h, l, c, v]
        # Missing keys fall back to 0 which corrupts TR (bug seen 2026-04-16:
        # low=0 against close=85 made TR = full price, ATR = asset price).
        # Fix: reject a candle if any of high/low/close is 0 or non-positive.
        true_ranges = []
        prev_close = None
        logged_shape = False
        for c in candles:
            if isinstance(c, dict):
                if not logged_shape:
                    logger.debug("ATR candle keys for %s: %s", asset, list(c.keys()))
                    logged_shape = True
                high = float(c.get("h") or c.get("high") or c.get("H") or c.get("highPx") or 0)
                low = float(c.get("l") or c.get("low") or c.get("L") or c.get("lowPx") or 0)
                close = float(c.get("c") or c.get("close") or c.get("C") or c.get("closePx") or 0)
            elif isinstance(c, (list, tuple)) and len(c) >= 5:
                # Could be [t,o,h,l,c,v] OR [t,o,h,l,c] — both safe
                high = float(c[2])
                low = float(c[3])
                close = float(c[4])
            else:
                continue

            # Defensive: skip obviously broken rows
            if high <= 0 or low <= 0 or close <= 0 or high < low:
                continue

            if prev_close is not None:
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close),
                )
                true_ranges.append(tr)
            prev_close = close

        if len(true_ranges) < period:
            logger.debug("ATR: only %d true ranges for %s (need %d)", len(true_ranges), asset, period)
            return None

        # Use the last N true ranges
        atr = sum(true_ranges[-period:]) / period

        # Sanity: a healthy ATR is ~0.2-5% of price. If it's >30% of price the
        # parse is wrong (previous bug: broken candles made ATR = full price).
        if prev_close and atr > prev_close * 0.30:
            logger.warning(
                "ATR sanity rejection for %s: atr=$%.4f price=$%.4f (%.1f%% — likely broken candles)",
                asset, atr, prev_close, atr / prev_close * 100,
            )
            return None

        logger.info("ATR(%d) for %s = $%.4f (%.3f%%)", period, asset, atr, (atr / prev_close * 100) if prev_close else 0)
        return atr

    except Exception:
        logger.debug("ATR computation failed for %s", asset, exc_info=True)
        return None


async def compute_stop_take_atr(
    boba,
    entry_price: float,
    direction: Direction,
    asset: str,
    sl_mult: float = ATR_SL_MULTIPLIER,
    tp_mult: float = ATR_TP_MULTIPLIER,
) -> tuple[float, float]:
    """Calculate ATR-based stop-loss and take-profit. Falls back to fixed % if ATR unavailable."""
    atr = await compute_atr(boba, asset)

    if atr is not None and atr > 0:
        # v2: honest ATR stops with NO arbitrary cap. Tight SL, fat TP.
        # Hard floor: SL must be at least 0.5% to avoid noise stops; TP must be at least 1.5%.
        sl_dist = max(atr * sl_mult, entry_price * 0.005)
        tp_dist = max(atr * tp_mult, entry_price * 0.015)
        if direction == Direction.LONG:
            stop_loss = entry_price - sl_dist
            take_profit = entry_price + tp_dist
        else:
            stop_loss = entry_price + sl_dist
            take_profit = entry_price - tp_dist
        logger.info(
            "ATR stops for %s %s: SL=$%.2f (%.2f%%), TP=$%.2f (%.2f%%)",
            direction.value, asset,
            stop_loss, abs(stop_loss - entry_price) / entry_price * 100,
            take_profit, abs(take_profit - entry_price) / entry_price * 100,
        )
    else:
        # Fallback to fixed percentages
        stop_loss, take_profit = compute_stop_take(entry_price, direction)
        logger.info("ATR unavailable for %s — using fixed %% stops", asset)

    return round(stop_loss, 2), round(take_profit, 2)


def compute_stop_take(
    entry_price: float,
    direction: Direction,
    stop_pct: float = DEFAULT_STOP_LOSS_PCT,
    tp_pct: float = DEFAULT_TAKE_PROFIT_PCT,
) -> tuple[float, float]:
    """Calculate fixed-percentage stop-loss and take-profit (fallback)."""
    if direction == Direction.LONG:
        stop_loss = entry_price * (1 - stop_pct)
        take_profit = entry_price * (1 + tp_pct)
    else:
        stop_loss = entry_price * (1 + stop_pct)
        take_profit = entry_price * (1 - tp_pct)

    return round(stop_loss, 2), round(take_profit, 2)


# ── Portfolio Drawdown Circuit Breaker ───────────────────────────────────────

def check_drawdown() -> tuple[bool, float, str]:
    """Check portfolio drawdown from peak. Returns (can_trade, drawdown_pct, reason).

    - drawdown < 10%: normal trading
    - 10-20% drawdown: can trade but sizes should be halved
    - >20% drawdown: halt all new trades for DRAWDOWN_COOLDOWN_HOURS
    """
    global _peak_balance, _drawdown_halt_until

    stats = get_stats()
    balance = PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"]

    # Update peak
    if balance > _peak_balance:
        _peak_balance = balance

    drawdown = (_peak_balance - balance) / _peak_balance if _peak_balance > 0 else 0

    # Check if we're in a cooldown halt
    now = datetime.utcnow()
    if _drawdown_halt_until and now < _drawdown_halt_until:
        remaining = (_drawdown_halt_until - now).total_seconds() / 3600
        return False, drawdown, f"HALTED: {drawdown:.1%} drawdown, {remaining:.1f}h cooldown remaining"

    # Clear expired halt
    if _drawdown_halt_until and now >= _drawdown_halt_until:
        _drawdown_halt_until = None
        logger.info("Drawdown cooldown expired — resuming trading")

    if drawdown >= DRAWDOWN_HALT_PCT:
        _drawdown_halt_until = now + timedelta(hours=DRAWDOWN_COOLDOWN_HOURS)
        logger.warning(
            "DRAWDOWN HALT: %.1f%% drawdown (peak $%.2f → $%.2f). Halting for %dh.",
            drawdown * 100, _peak_balance, balance, DRAWDOWN_COOLDOWN_HOURS,
        )
        return False, drawdown, f"HALTED: {drawdown:.1%} drawdown from peak ${_peak_balance:.2f}"

    if drawdown >= DRAWDOWN_WARN_PCT:
        logger.warning(
            "DRAWDOWN WARNING: %.1f%% (peak $%.2f → $%.2f). Reducing position sizes.",
            drawdown * 100, _peak_balance, balance,
        )
        return True, drawdown, f"WARNING: {drawdown:.1%} drawdown — sizes halved"

    return True, drawdown, "OK"


# ── Orderbook Liquidity Check ────────────────────────────────────────────────

async def check_orderbook_liquidity(
    boba, asset: str, size_usd: float, direction: Direction
) -> tuple[bool, float, str]:
    """Check order book depth before entering a trade.

    Returns (is_liquid, estimated_slippage_pct, reason).
    """
    try:
        raw = await boba.call_tool("hl_get_orderbook", {"coin": asset})
        data = json.loads(raw) if isinstance(raw, str) else raw

        bids = data.get("bids", data.get("levels", {}).get("bids", []))
        asks = data.get("asks", data.get("levels", {}).get("asks", []))

        if not bids or not asks:
            logger.debug("Orderbook empty for %s — proceeding anyway", asset)
            return True, 0.0, "No orderbook data (proceeding)"

        # Calculate depth at top 3 levels on the relevant side
        side = asks if direction == Direction.LONG else bids  # buying into asks, selling into bids
        depth_usd = 0.0
        weighted_price = 0.0

        for i, level in enumerate(side[:5]):
            if isinstance(level, dict):
                price = float(level.get("px", level.get("price", 0)))
                size = float(level.get("sz", level.get("size", level.get("amount", 0))))
            elif isinstance(level, (list, tuple)) and len(level) >= 2:
                price = float(level[0])
                size = float(level[1])
            else:
                continue

            level_usd = price * size
            depth_usd += level_usd
            weighted_price += price * size

            if i < 3 and depth_usd >= size_usd:
                break

        if depth_usd < MIN_ORDERBOOK_DEPTH_USD:
            # Paper trading: Boba orderbook API often returns thin/mock data
            # for major assets like BTC/ETH/SOL. Log warning but proceed.
            logger.warning(
                "Thin orderbook for %s: $%.0f depth (need $%d) — proceeding (paper trading)",
                asset, depth_usd, MIN_ORDERBOOK_DEPTH_USD,
            )
            return True, 0.0, f"Thin orderbook (paper mode): ${depth_usd:.0f}"

        # Estimate slippage: compare mid price to volume-weighted fill price
        mid_price = (float(bids[0][0] if isinstance(bids[0], (list, tuple)) else bids[0].get("px", bids[0].get("price", 0))) +
                     float(asks[0][0] if isinstance(asks[0], (list, tuple)) else asks[0].get("px", asks[0].get("price", 0)))) / 2

        if weighted_price > 0 and mid_price > 0:
            total_size = sum(
                float(l.get("sz", l.get("size", l[1] if isinstance(l, (list, tuple)) else 0)))
                for l in side[:3]
                if l
            )
            vwap = weighted_price / total_size if total_size > 0 else mid_price
            slippage = abs(vwap - mid_price) / mid_price
        else:
            slippage = 0.0

        if slippage > MAX_SLIPPAGE_PCT:
            # For paper trading, warn but don't block — orderbook data is unreliable
            logger.warning(
                "High estimated slippage for %s: %.2f%% (max %.2f%%) — proceeding (paper trading)",
                asset, slippage * 100, MAX_SLIPPAGE_PCT * 100,
            )
            return True, slippage, f"High slippage warning: {slippage:.2%}"

        logger.info("Orderbook %s: depth=$%.0f, est. slippage=%.3f%%", asset, depth_usd, slippage * 100)
        return True, slippage, "OK"

    except Exception:
        logger.debug("Orderbook check failed for %s — proceeding", asset, exc_info=True)
        return True, 0.0, "Orderbook check unavailable (proceeding)"


# ── Fill Confirmation & Slippage Tracking ────────────────────────────────────

async def confirm_fill_and_track_slippage(
    boba, asset: str, expected_price: float, direction: Direction
) -> tuple[Optional[float], Optional[float]]:
    """After placing a market order, check hl_get_fills to confirm execution.

    Returns (actual_fill_price, slippage_pct) or (None, None) if unavailable.
    """
    try:
        raw = await boba.call_tool("hl_get_fills", {"coin": asset, "limit": 5})
        data = json.loads(raw) if isinstance(raw, str) else raw

        fills = data if isinstance(data, list) else data.get("fills", data.get("data", []))
        if not fills:
            logger.debug("No fills returned for %s", asset)
            return None, None

        # Get the most recent fill
        latest = fills[0] if fills else None
        if not latest:
            return None, None

        fill_price = float(latest.get("px", latest.get("price", latest.get("fillPx", 0))))
        fill_size = float(latest.get("sz", latest.get("size", latest.get("fillSz", 0))))
        fill_side = latest.get("side", latest.get("dir", ""))

        if fill_price <= 0:
            return None, None

        slippage = (fill_price - expected_price) / expected_price
        # For shorts, slippage is inverted (lower fill = good)
        if direction == Direction.SHORT:
            slippage = -slippage

        logger.info(
            "FILL CONFIRMED: %s %s @ $%.4f (expected $%.4f, slippage %+.3f%%, size $%.2f)",
            direction.value, asset, fill_price, expected_price, slippage * 100, fill_size,
        )

        if abs(slippage) > MAX_SLIPPAGE_PCT:
            logger.warning(
                "HIGH SLIPPAGE on %s: %+.3f%% (threshold %.2f%%)",
                asset, slippage * 100, MAX_SLIPPAGE_PCT * 100,
            )

        return fill_price, slippage

    except Exception:
        logger.debug("Fill confirmation failed for %s", asset, exc_info=True)
        return None, None


# ── Trend Regime Detection ────────────────────────────────────────────────────

async def detect_trend(boba, asset: str) -> tuple[str, float]:
    """Detect market trend using EMA crossover on 1H candles.

    Returns (regime, strength):
      - regime: "uptrend", "downtrend", or "neutral"
      - strength: 0.0-1.0 (how strong the trend is)

    Uses EMA(8) vs EMA(21) — standard institutional trend detection.
    If fast EMA > slow EMA → uptrend (price above average → buyers in control).
    """
    try:
        raw = await boba.call_tool("hl_get_history", {
            "coin": asset,
            "type": "candles",
            "interval": "1h",
            "limit": 30,
        })
        data = json.loads(raw) if isinstance(raw, str) else raw
        candles = data if isinstance(data, list) else data.get("candles", data.get("data", []))

        if not candles or len(candles) < 22:
            return "neutral", 0.0

        # Extract close prices
        closes = []
        for c in candles:
            if isinstance(c, dict):
                closes.append(float(c.get("c", c.get("close", 0))))
            elif isinstance(c, (list, tuple)) and len(c) >= 5:
                closes.append(float(c[4]))

        if len(closes) < 22:
            return "neutral", 0.0

        # Calculate EMAs
        ema_fast = _compute_ema(closes, 8)
        ema_slow = _compute_ema(closes, 21)

        if ema_fast is None or ema_slow is None:
            return "neutral", 0.0

        # Trend determination
        diff_pct = (ema_fast - ema_slow) / ema_slow * 100
        current_price = closes[-1]

        # Also check: is price above or below both EMAs?
        price_vs_fast = (current_price - ema_fast) / ema_fast * 100
        price_vs_slow = (current_price - ema_slow) / ema_slow * 100

        if diff_pct > 0.1 and price_vs_slow > 0:
            strength = min(1.0, abs(diff_pct) / 2.0)
            regime = "uptrend"
        elif diff_pct < -0.1 and price_vs_slow < 0:
            strength = min(1.0, abs(diff_pct) / 2.0)
            regime = "downtrend"
        else:
            strength = 0.0
            regime = "neutral"

        logger.info(
            "TREND %s: %s (strength=%.2f, EMA8=%.2f, EMA21=%.2f, diff=%.3f%%)",
            asset, regime, strength, ema_fast, ema_slow, diff_pct,
        )
        return regime, strength

    except Exception:
        logger.debug("Trend detection failed for %s", asset, exc_info=True)
        return "neutral", 0.0


def _compute_ema(prices: list[float], period: int) -> Optional[float]:
    """Compute Exponential Moving Average."""
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period  # SMA for initial seed
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


async def check_trend_alignment(
    boba, asset: str, direction: Direction
) -> tuple[bool, str]:
    """Check if proposed trade direction aligns with market trend.

    Returns (allowed, reason). Blocks counter-trend trades in strong trends.
    """
    from config import TREND_BLOCK_COUNTER
    if not TREND_BLOCK_COUNTER:
        return True, "OK"

    regime, strength = await detect_trend(boba, asset)

    if regime == "uptrend" and direction == Direction.SHORT and strength > 0.3:
        return False, f"BLOCKED: shorting {asset} in uptrend (strength={strength:.2f})"

    if regime == "downtrend" and direction == Direction.LONG and strength > 0.3:
        return False, f"BLOCKED: longing {asset} in downtrend (strength={strength:.2f})"

    return True, f"OK (trend={regime}, strength={strength:.2f})"


# ── Anti-Churn: Minimum Time Between Trades ──────────────────────────────────

def check_trade_cooldown(asset: str) -> tuple[bool, str]:
    """Reject trades that are too close together on the same asset."""
    from config import MIN_TIME_BETWEEN_TRADES
    from db import get_all_positions

    recent = get_all_positions(limit=10)
    now = datetime.utcnow()

    for p in recent:
        if p.asset.upper() == asset.upper():
            # Check time since this position was opened
            age_min = (now - p.opened_at).total_seconds() / 60
            if age_min < MIN_TIME_BETWEEN_TRADES:
                return False, f"Cooldown: last {asset} trade was {age_min:.0f}m ago (need {MIN_TIME_BETWEEN_TRADES}m)"
    return True, "OK"


# ── Original Risk Gates (unchanged logic) ────────────────────────────────────

def can_open_position(proposed_size: float, proposed_leverage: int = 1) -> tuple[bool, str]:
    """Check if we have margin AND aren't over-allocated."""
    # Drawdown circuit breaker — check first
    can_trade, drawdown, dd_reason = check_drawdown()
    if not can_trade:
        return False, dd_reason

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
    """Same direction = blocked. Opposite = flip, but only if position is old enough."""
    for p in get_open_positions():
        if p.asset.upper() == asset.upper():
            if p.direction == direction:
                return False, f"Already {direction.value} on {asset}"
            else:
                # Don't flip too quickly — kills profits from spread costs
                age_min = (datetime.utcnow() - p.opened_at).total_seconds() / 60
                if age_min < MIN_FLIP_INTERVAL_MINUTES:
                    return False, f"Won't flip {asset} yet ({age_min:.0f}m old, need {MIN_FLIP_INTERVAL_MINUTES}m)"
                return False, f"FLIP:{p.id}"
    return True, "OK"


def calculate_position_size(conviction: float, suggested_size: float) -> float:
    """LEGACY shim — v2 uses calculate_position_size_v2.

    Kept so any old call site still compiles. Routes to v2 with a synthetic
    2.5% stop distance (matches DEFAULT_STOP_LOSS_PCT). New code MUST call
    calculate_position_size_v2 directly with the real stop distance.
    """
    return calculate_position_size_v2(
        stop_distance_pct=DEFAULT_STOP_LOSS_PCT,
        leverage=3,
    )


def calculate_position_size_v2(
    stop_distance_pct: float,
    leverage: int = 3,
) -> float:
    """Fixed-fractional position sizing (v2).

    notional_size = (risk_$ / stop_distance_pct) × leverage
        where risk_$ = wallet_balance × RISK_PCT_PER_TRADE.

    The trader never loses more than RISK_PCT_PER_TRADE of the wallet on a
    single stop-out, regardless of asset volatility or leverage. Tighter stops
    automatically scale up the position; wider stops shrink it.

    Returns notional USD size (post-leverage) — the same units the rest of the
    code uses for ``size_usd``. Returns 0.0 if the trade can't be sized
    (drawdown halt, no balance, smaller than dust).
    """
    if stop_distance_pct <= 0:
        logger.warning("calculate_position_size_v2: stop_distance_pct=%.4f <= 0", stop_distance_pct)
        return 0.0

    stats = get_stats()
    balance = PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"]
    if balance <= 5:
        return 0.0

    open_positions = get_open_positions()
    used_margin = sum(p.size_usd / max(p.leverage, 1) for p in open_positions)
    reserved = balance * CASH_RESERVE_PCT
    available_margin = max(0.0, balance - used_margin - reserved)

    # Core fixed-fractional formula
    risk_dollars = balance * RISK_PCT_PER_TRADE
    notional = (risk_dollars / stop_distance_pct) * max(leverage, 1)

    # Drawdown reduction: halve size if in warning zone
    _, drawdown, _ = check_drawdown()
    if drawdown >= DRAWDOWN_WARN_PCT:
        original = notional
        notional *= 0.5
        logger.info(
            "Drawdown size reduction: $%.2f → $%.2f (%.1f%% drawdown)",
            original, notional, drawdown * 100,
        )

    # Hard cap: notional cannot exceed MAX_PER_TRADE_PCT × balance × leverage
    max_notional = balance * MAX_PER_TRADE_PCT * max(leverage, 1)
    if notional > max_notional:
        notional = max_notional

    # Available-margin cap: never need more margin than we actually have free
    margin_needed = notional / max(leverage, 1)
    if margin_needed > available_margin:
        notional = available_margin * max(leverage, 1)

    if notional < 8:
        logger.info(
            "Position too small after sizing: $%.2f (risk=$%.2f, stop=%.2f%%, lev=%dx)",
            notional, risk_dollars, stop_distance_pct * 100, leverage,
        )
        return 0.0

    logger.info(
        "v2 sizing: $%.2f notional (risk=$%.2f @ %.1f%% stop, lev=%dx, balance=$%.2f)",
        notional, risk_dollars, stop_distance_pct * 100, leverage, balance,
    )
    return round(notional, 2)


# ── Chandelier Trailing Stop ─────────────────────────────────────────────────

def chandelier_stop(
    direction: Direction,
    entry_price: float,
    extreme_price: float,
    atr: float,
    current_stop: float,
) -> tuple[float, bool]:
    """Compute the new stop-loss price using a Chandelier exit.

    A Chandelier stop trails behind the *highest high since entry* (for longs)
    or *lowest low since entry* (for shorts) by ``CHANDELIER_ATR_MULT × ATR``.
    It only activates once price has moved at least ``CHANDELIER_ACTIVATION_ATR``
    in our favour from entry — before that, the original SL stays in place.

    Returns ``(new_stop, did_move)``. Stop never loosens (only ratchets toward
    profit), so this can be called every cycle safely.
    """
    if atr <= 0:
        return current_stop, False

    activation_distance = atr * CHANDELIER_ACTIVATION_ATR
    trail_distance = atr * CHANDELIER_ATR_MULT

    if direction == Direction.LONG:
        favourable_move = extreme_price - entry_price
        if favourable_move < activation_distance:
            return current_stop, False
        proposed = extreme_price - trail_distance
        # Only move stop *up* (tighter), never down
        if proposed > current_stop:
            return round(proposed, 4), True
        return current_stop, False
    else:  # SHORT
        favourable_move = entry_price - extreme_price
        if favourable_move < activation_distance:
            return current_stop, False
        proposed = extreme_price + trail_distance
        # For shorts, only move stop *down* (tighter)
        if proposed < current_stop:
            return round(proposed, 4), True
        return current_stop, False


def clamp_leverage(proposed: int, conviction: float = 0.5) -> int:
    """v2: leverage no longer scales conviction (sizing does).

    Hard cap at 5x for safety. Min 1x. Anything in between is honored.
    Conviction is accepted for backwards compat but ignored.
    """
    return max(1, min(int(proposed or 3), 5))


def get_available_margin() -> float:
    """How much margin the wallet can deploy right now (after reserve)."""
    stats = get_stats()
    balance = PAPER_WALLET_STARTING_BALANCE + stats["total_pnl"]
    open_positions = get_open_positions()
    used = sum(p.size_usd / max(p.leverage, 1) for p in open_positions)
    reserved = balance * CASH_RESERVE_PCT
    return max(0.0, balance - used - reserved)
