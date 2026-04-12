"""Multi-source signal scoring (v2).

Single source of truth for whether to fire a trade. Combines four edge
sources into a directional score in [-N, +N]. A trade fires when the
absolute total exceeds the asset's threshold (higher bar for majors).

Score components:
  - funding   ∈ [-1, +1]   (extreme HL funding → contrarian; sign opposes the crowd)
  - polymarket ∈ [-0.6, +0.6]  (PM probability shift, direction-corrected)
  - kol       ∈ [-0.6, +0.6]  (whale flow alignment from Boba get_kol_swaps)
  - trend     ∈ [-0.4, +0.4]  (EMA8/21 alignment penalty/bonus)

Sign convention: positive = long, negative = short.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from config import (
    ASSET_MAJORS,
    FUNDING_EXTREME_THRESHOLD,
    SCORE_THRESHOLD_ALTS,
    SCORE_THRESHOLD_MAJORS,
    SCORE_WEIGHT_FUNDING,
    SCORE_WEIGHT_KOL,
    SCORE_WEIGHT_POLYMARKET,
    SCORE_WEIGHT_TREND,
    TRADABLE_ASSETS,
)
from db import get_kol_signals_for_asset
from models import Direction
from risk import detect_trend

logger = logging.getLogger(__name__)


@dataclass
class TradeScore:
    """Result of evaluating all signal sources for one asset."""

    asset: str
    score_funding: float = 0.0
    score_polymarket: float = 0.0
    score_kol: float = 0.0
    score_trend: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return (
            self.score_funding
            + self.score_polymarket
            + self.score_kol
            + self.score_trend
        )

    @property
    def direction(self) -> Direction:
        return Direction.LONG if self.total >= 0 else Direction.SHORT

    @property
    def confidence(self) -> float:
        """Magnitude of total score, useful as a 0..N conviction proxy."""
        return abs(self.total)

    def threshold(self) -> float:
        return (
            SCORE_THRESHOLD_MAJORS
            if self.asset.upper() in ASSET_MAJORS
            else SCORE_THRESHOLD_ALTS
        )

    def passes(self) -> bool:
        return self.confidence >= self.threshold()

    def explain(self) -> str:
        return (
            f"{self.asset} {self.direction.value} total={self.total:+.2f} "
            f"(thr={self.threshold():.2f}) "
            f"[fund={self.score_funding:+.2f} pm={self.score_polymarket:+.2f} "
            f"kol={self.score_kol:+.2f} trend={self.score_trend:+.2f}] "
            + " | ".join(self.notes)
        )

    def to_attribution(self) -> dict:
        return {
            "score_funding": self.score_funding,
            "score_polymarket": self.score_polymarket,
            "score_kol": self.score_kol,
            "score_trend": self.score_trend,
            "score_total": self.total,
            "direction": self.direction.value,
            "notes": " | ".join(self.notes)[:500],
        }


# ── Per-source scoring ───────────────────────────────────────────────────────

def score_funding(hl_rate: Optional[float]) -> float:
    """Score from HL predicted funding rate.

    Convention: HL funding is per 8h. Positive funding = longs pay shorts =
    crowd is long → contrarian SHORT (negative score). Negative funding =
    shorts pay longs = crowd is short → contrarian LONG (positive score).

    Output: −1.0 .. +1.0 weighted by SCORE_WEIGHT_FUNDING.
    """
    if hl_rate is None:
        return 0.0
    if abs(hl_rate) < FUNDING_EXTREME_THRESHOLD * 0.5:
        # Below half-threshold = no signal
        return 0.0
    # Normalize: rate / (2 × threshold) gives roughly ±1 at strong extremes
    raw = -hl_rate / (FUNDING_EXTREME_THRESHOLD * 2)
    raw = max(-1.0, min(1.0, raw))
    return raw * SCORE_WEIGHT_FUNDING


def score_polymarket(price_change_pct: Optional[float], direction_hint: Optional[Direction]) -> float:
    """Score from Polymarket signal.

    Caller passes the direction the signal *implies* (after the dip/reach
    interpretation logic in agent.py). We just convert magnitude → score.

    Magnitude maps as:
      |move| < 4%  → 0.0
      |move| 4-8%  → 0.3 × weight
      |move| 8-15% → 0.7 × weight
      |move| >15%  → 1.0 × weight
    """
    if price_change_pct is None or direction_hint is None:
        return 0.0
    mag = abs(price_change_pct)
    if mag < 0.04:
        return 0.0
    if mag < 0.08:
        intensity = 0.3
    elif mag < 0.15:
        intensity = 0.7
    else:
        intensity = 1.0
    sign = 1.0 if direction_hint == Direction.LONG else -1.0
    return sign * intensity * SCORE_WEIGHT_POLYMARKET


def score_kol(asset: str, lookback_minutes: int = 60) -> float:
    """Score from KOL whale flow over recent window.

    Counts long vs short whale signals for the asset; the imbalance
    (longs − shorts) / max(total, 1) becomes the directional score.
    """
    signals = get_kol_signals_for_asset(asset, minutes=lookback_minutes)
    if not signals:
        return 0.0
    longs = sum(1 for s in signals if s.direction == Direction.LONG)
    shorts = sum(1 for s in signals if s.direction == Direction.SHORT)
    total = longs + shorts
    if total == 0:
        return 0.0
    imbalance = (longs - shorts) / total
    # Saturate fast: 3+ aligned signals already gives full score
    intensity = min(1.0, total / 3.0)
    return imbalance * intensity * SCORE_WEIGHT_KOL


async def score_trend_async(boba, asset: str) -> float:
    """Score from EMA8/21 trend alignment on 1h candles.

    Reuses risk.detect_trend → ("uptrend"|"downtrend"|"neutral", strength).
    Output: ±strength × SCORE_WEIGHT_TREND.
    """
    try:
        regime, strength = await detect_trend(boba, asset)
    except Exception:
        logger.debug("Trend detection failed for %s", asset, exc_info=True)
        return 0.0

    if regime == "uptrend":
        return strength * SCORE_WEIGHT_TREND
    if regime == "downtrend":
        return -strength * SCORE_WEIGHT_TREND
    return 0.0


# ── Composite evaluator ──────────────────────────────────────────────────────

async def evaluate_trade(
    boba,
    asset: str,
    *,
    hl_funding_rate: Optional[float] = None,
    pm_price_change: Optional[float] = None,
    pm_direction_hint: Optional[Direction] = None,
) -> TradeScore:
    """Compute the full multi-source score for one asset.

    Caller supplies whatever they already know (e.g. funding from a trigger
    event, or PM data from a signal). Missing inputs simply contribute 0.
    KOL and trend are always pulled internally.
    """
    asset_u = asset.upper()
    score = TradeScore(asset=asset_u)

    if asset_u not in TRADABLE_ASSETS:
        score.notes.append(f"REJECTED: {asset_u} not in TRADABLE_ASSETS")
        return score

    # Funding
    if hl_funding_rate is not None:
        score.score_funding = score_funding(hl_funding_rate)
        if score.score_funding != 0:
            score.notes.append(
                f"funding {hl_funding_rate * 100:+.4f}%/8h → {score.score_funding:+.2f}"
            )

    # Polymarket
    if pm_price_change is not None and pm_direction_hint is not None:
        score.score_polymarket = score_polymarket(pm_price_change, pm_direction_hint)
        if score.score_polymarket != 0:
            score.notes.append(
                f"PM {pm_price_change * 100:+.1f}% {pm_direction_hint.value} → {score.score_polymarket:+.2f}"
            )

    # KOL
    score.score_kol = score_kol(asset_u, lookback_minutes=60)
    if score.score_kol != 0:
        score.notes.append(f"KOL flow → {score.score_kol:+.2f}")

    # Trend
    score.score_trend = await score_trend_async(boba, asset_u)
    if score.score_trend != 0:
        score.notes.append(f"trend → {score.score_trend:+.2f}")

    return score
