"""Pydantic data models for SignalFlow."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    STOPPED = "stopped"


# ── Signal ────────────────────────────────────────────────────────────────────

class Signal(BaseModel):
    """A detected price movement on a Polymarket prediction market."""

    id: Optional[int] = None
    market_id: str
    market_question: str
    current_price: float
    price_change_pct: float
    timeframe_minutes: int
    category: str = ""
    detected_at: datetime = Field(default_factory=datetime.utcnow)


# ── Analysis ──────────────────────────────────────────────────────────────────

class Analysis(BaseModel):
    """Claude's analysis of a signal — includes reasoning and trade suggestion."""

    id: Optional[int] = None
    signal_id: int
    reasoning: str
    conviction_score: float = Field(ge=0.0, le=1.0)
    suggested_direction: Direction
    suggested_asset: str
    suggested_size_usd: float
    risk_notes: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Position ──────────────────────────────────────────────────────────────────

class Position(BaseModel):
    """A live or historical perps position on Hyperliquid."""

    id: Optional[int] = None
    analysis_id: int
    asset: str
    direction: Direction
    entry_price: float
    size_usd: float
    leverage: int
    stop_loss: float
    take_profit: float
    status: PositionStatus = PositionStatus.OPEN
    pnl: float = 0.0
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None


# ── Position Snapshot ─────────────────────────────────────────────────────────

class PositionSnapshot(BaseModel):
    """Track PnL for a position at a point in time (one per cycle per position)."""

    id: Optional[int] = None
    position_id: int
    asset: str
    current_price: float
    unrealized_pnl: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── KOL Signal ────────────────────────────────────────────────────────────────

class KolSignal(BaseModel):
    """A significant trade detected from a KOL (Key Opinion Leader) wallet."""

    id: Optional[int] = None
    kol_name: str
    wallet_address: str
    asset: str
    direction: Direction
    trade_size_usd: float
    detected_at: datetime = Field(default_factory=datetime.utcnow)


# ── Wallet Snapshot ──────────────────────────────────────────────────────────

class WalletSnapshot(BaseModel):
    """Point-in-time snapshot of the paper trading wallet."""
    id: Optional[int] = None
    balance: float
    total_pnl: float
    open_positions: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Agent Decision (one per cycle) ───────────────────────────────────────────

class AgentDecision(BaseModel):
    """Summary of what the agent did in a single cycle."""

    id: Optional[int] = None
    cycle_id: str
    signals_detected: int = 0
    analyses_produced: int = 0
    trades_executed: int = 0
    reasoning_summary: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── v3: Trade Proposals ─────────────────────────────────────────────────────

class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"


class TradeProposal(BaseModel):
    """A specialist agent's trade proposal, awaiting orchestrator decision."""

    id: Optional[int] = None
    agent_id: str                                      # 'pm_analyst', 'funding_analyst', etc.
    asset: str
    direction: Direction
    conviction: float = Field(ge=0.0, le=1.0)
    edge_type: str = ""                                # 'sentiment', 'funding', 'oi_flow', 'momentum', 'mean_revert'
    reasoning: str
    suggested_risk_pct: float = 0.015
    timeframe_hours: float = 4.0
    invalidation: str = ""
    status: ProposalStatus = ProposalStatus.PENDING
    allocated_risk_pct: Optional[float] = None         # set by orchestrator on approval
    orchestrator_reason: str = ""                      # why approved/rejected
    created_at: datetime = Field(default_factory=datetime.utcnow)
    decided_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None


# ── v3: Regime Assessments ──────────────────────────────────────────────────

class RegimeType(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"


class RegimeAssessment(BaseModel):
    """Trend Analyst's view of the market regime for an asset."""

    id: Optional[int] = None
    asset: str
    regime: RegimeType
    strength: float = 0.0
    support: Optional[float] = None
    resistance: Optional[float] = None
    atr_expanding: bool = False
    recommendation: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
