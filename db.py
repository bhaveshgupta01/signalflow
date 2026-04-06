"""Supabase persistence layer for SignalFlow.

Replaces the original SQLite layer. Same function signatures — all callers
(agent.py, risk.py, signals.py, kol_tracker.py, runner.py, dashboard pages)
work without changes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from supabase import create_client, Client

from models import (
    AgentDecision,
    Analysis,
    Direction,
    KolSignal,
    Position,
    PositionSnapshot,
    PositionStatus,
    Signal,
    WalletSnapshot,
)
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def _parse_dt(val: str | None) -> datetime | None:
    """Parse a Postgres TIMESTAMPTZ string into a datetime."""
    if val is None:
        return None
    return datetime.fromisoformat(val)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cutoff_iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """No-op — schema is managed via Supabase migrations."""
    _get_client()  # validate connection on startup


# ── Signals ───────────────────────────────────────────────────────────────────

def save_signal(s: Signal) -> Signal:
    client = _get_client()
    data = {
        "market_id": s.market_id,
        "market_question": s.market_question,
        "current_price": s.current_price,
        "price_change_pct": s.price_change_pct,
        "timeframe_minutes": s.timeframe_minutes,
        "category": s.category,
        "detected_at": s.detected_at.isoformat(),
    }
    result = client.table("signals").insert(data).execute()
    s.id = result.data[0]["id"]
    return s


def get_recent_signals(minutes: int = 30) -> list[Signal]:
    client = _get_client()
    cutoff = _cutoff_iso(minutes)
    result = (
        client.table("signals")
        .select("*")
        .gte("detected_at", cutoff)
        .order("detected_at", desc=True)
        .execute()
    )
    return [_row_to_signal(r) for r in result.data]


def get_signals_for_market(market_id: str, minutes: int = 30) -> list[Signal]:
    client = _get_client()
    cutoff = _cutoff_iso(minutes)
    result = (
        client.table("signals")
        .select("*")
        .eq("market_id", market_id)
        .gte("detected_at", cutoff)
        .order("detected_at", desc=True)
        .execute()
    )
    return [_row_to_signal(r) for r in result.data]


# ── Analyses ──────────────────────────────────────────────────────────────────

def save_analysis(a: Analysis) -> Analysis:
    client = _get_client()
    data = {
        "signal_id": a.signal_id,
        "reasoning": a.reasoning,
        "conviction_score": a.conviction_score,
        "suggested_direction": a.suggested_direction.value,
        "suggested_asset": a.suggested_asset,
        "suggested_size_usd": a.suggested_size_usd,
        "risk_notes": a.risk_notes,
        "created_at": a.created_at.isoformat(),
    }
    result = client.table("analyses").insert(data).execute()
    a.id = result.data[0]["id"]
    return a


def get_recent_analyses(limit: int = 20) -> list[Analysis]:
    client = _get_client()
    result = (
        client.table("analyses")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_analysis(r) for r in result.data]


# ── Positions ─────────────────────────────────────────────────────────────────

def save_position(p: Position) -> Position:
    client = _get_client()
    data = {
        "analysis_id": p.analysis_id,
        "asset": p.asset,
        "direction": p.direction.value,
        "entry_price": p.entry_price,
        "size_usd": p.size_usd,
        "leverage": p.leverage,
        "stop_loss": p.stop_loss,
        "take_profit": p.take_profit,
        "status": p.status.value,
        "pnl": p.pnl,
        "opened_at": p.opened_at.isoformat(),
        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
    }
    result = client.table("positions").insert(data).execute()
    p.id = result.data[0]["id"]
    return p


def update_position(position_id: int, *, status: Optional[PositionStatus] = None,
                     pnl: Optional[float] = None, closed_at: Optional[datetime] = None,
                     stop_loss: Optional[float] = None) -> None:
    client = _get_client()
    updates: dict = {}
    if status is not None:
        updates["status"] = status.value
    if pnl is not None:
        updates["pnl"] = pnl
    if closed_at is not None:
        updates["closed_at"] = closed_at.isoformat()
    if stop_loss is not None:
        updates["stop_loss"] = stop_loss
    if not updates:
        return
    client.table("positions").update(updates).eq("id", position_id).execute()


def get_open_positions() -> list[Position]:
    client = _get_client()
    result = (
        client.table("positions")
        .select("*")
        .eq("status", "open")
        .order("opened_at", desc=True)
        .execute()
    )
    return [_row_to_position(r) for r in result.data]


def get_last_trade_time() -> datetime | None:
    """Return the opened_at of the most recent position, or None if no trades."""
    client = _get_client()
    result = (
        client.table("positions")
        .select("opened_at")
        .order("opened_at", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        return _parse_dt(result.data[0]["opened_at"])
    return None


def get_all_positions(limit: int = 50) -> list[Position]:
    client = _get_client()
    result = (
        client.table("positions")
        .select("*")
        .order("opened_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_position(r) for r in result.data]


# ── Agent Decisions ───────────────────────────────────────────────────────────

def save_decision(d: AgentDecision) -> AgentDecision:
    client = _get_client()
    data = {
        "cycle_id": d.cycle_id,
        "signals_detected": d.signals_detected,
        "analyses_produced": d.analyses_produced,
        "trades_executed": d.trades_executed,
        "reasoning_summary": d.reasoning_summary,
        "timestamp": d.timestamp.isoformat(),
    }
    result = client.table("agent_decisions").insert(data).execute()
    d.id = result.data[0]["id"]
    return d


def get_recent_decisions(limit: int = 20) -> list[AgentDecision]:
    client = _get_client()
    result = (
        client.table("agent_decisions")
        .select("*")
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_decision(r) for r in result.data]


# ── KOL Signals ──────────────────────────────────────────────────────────────

def save_kol_signal(k: KolSignal) -> KolSignal:
    client = _get_client()
    data = {
        "kol_name": k.kol_name,
        "wallet_address": k.wallet_address,
        "asset": k.asset,
        "direction": k.direction.value,
        "trade_size_usd": k.trade_size_usd,
        "detected_at": k.detected_at.isoformat(),
    }
    result = client.table("kol_signals").insert(data).execute()
    k.id = result.data[0]["id"]
    return k


def get_recent_kol_signals(minutes: int = 60) -> list[KolSignal]:
    client = _get_client()
    cutoff = _cutoff_iso(minutes)
    result = (
        client.table("kol_signals")
        .select("*")
        .gte("detected_at", cutoff)
        .order("detected_at", desc=True)
        .execute()
    )
    return [_row_to_kol_signal(r) for r in result.data]


def get_kol_signals_for_asset(asset: str, minutes: int = 60) -> list[KolSignal]:
    client = _get_client()
    cutoff = _cutoff_iso(minutes)
    result = (
        client.table("kol_signals")
        .select("*")
        .ilike("asset", asset)
        .gte("detected_at", cutoff)
        .order("detected_at", desc=True)
        .execute()
    )
    return [_row_to_kol_signal(r) for r in result.data]


def get_all_kol_signals(limit: int = 50) -> list[KolSignal]:
    client = _get_client()
    result = (
        client.table("kol_signals")
        .select("*")
        .order("detected_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_kol_signal(r) for r in result.data]


# ── Position Snapshots ────────────────────────────────────────────────────────

def save_position_snapshot(ps: PositionSnapshot) -> PositionSnapshot:
    client = _get_client()
    data = {
        "position_id": ps.position_id,
        "asset": ps.asset,
        "current_price": ps.current_price,
        "unrealized_pnl": ps.unrealized_pnl,
        "timestamp": ps.timestamp.isoformat(),
    }
    result = client.table("position_snapshots").insert(data).execute()
    ps.id = result.data[0]["id"]
    return ps


def get_position_snapshots(position_id: int | None = None, minutes: int = 1440) -> list[PositionSnapshot]:
    client = _get_client()
    cutoff = _cutoff_iso(minutes)
    query = client.table("position_snapshots").select("*").gte("timestamp", cutoff)
    if position_id:
        query = query.eq("position_id", position_id)
    result = query.order("timestamp").execute()
    return [_row_to_position_snapshot(r) for r in result.data]


def get_asset_pnl_history(minutes: int = 1440) -> dict[str, list[tuple]]:
    """Return {asset: [(timestamp, sum_pnl), ...]} for charting."""
    client = _get_client()
    cutoff = _cutoff_iso(minutes)
    result = client.rpc("get_asset_pnl_history", {"cutoff_ts": cutoff}).execute()
    output: dict[str, list[tuple]] = {}
    for r in result.data:
        asset = r["asset"]
        if asset not in output:
            output[asset] = []
        output[asset].append((_parse_dt(r["ts"]), r["total_pnl"]))
    return output


# ── Wallet Snapshots ─────────────────────────────────────────────────────────

def save_wallet_snapshot(ws: WalletSnapshot) -> WalletSnapshot:
    client = _get_client()
    data = {
        "balance": ws.balance,
        "total_pnl": ws.total_pnl,
        "open_positions": ws.open_positions,
        "timestamp": ws.timestamp.isoformat(),
    }
    result = client.table("wallet_snapshots").insert(data).execute()
    ws.id = result.data[0]["id"]
    return ws


def get_wallet_history(limit: int = 100) -> list[WalletSnapshot]:
    client = _get_client()
    result = (
        client.table("wallet_snapshots")
        .select("*")
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_wallet_snapshot(r) for r in result.data]


# ── Aggregate Stats ───────────────────────────────────────────────────────────

def get_stats() -> dict:
    client = _get_client()
    result = client.rpc("get_trading_stats").execute()
    return result.data


# ── Trade Events (for chart annotations) ────────────────────────────────────

def get_trade_events(minutes: int = 999999) -> list[dict]:
    """Return trade open/close events for chart annotations."""
    client = _get_client()
    cutoff = _cutoff_iso(minutes)
    events = []

    # Open events
    open_result = (
        client.table("positions")
        .select("id, asset, direction, entry_price, size_usd, leverage, opened_at")
        .gte("opened_at", cutoff)
        .order("opened_at")
        .execute()
    )
    for r in open_result.data:
        events.append({
            "type": "open",
            "position_id": r["id"],
            "asset": r["asset"],
            "direction": r["direction"],
            "price": r["entry_price"],
            "size_usd": r["size_usd"],
            "leverage": r["leverage"],
            "timestamp": _parse_dt(r["opened_at"]),
        })

    # Close events
    close_result = (
        client.table("positions")
        .select("id, asset, direction, entry_price, size_usd, pnl, status, closed_at")
        .not_.is_("closed_at", "null")
        .gte("closed_at", cutoff)
        .order("closed_at")
        .execute()
    )
    for r in close_result.data:
        events.append({
            "type": "close",
            "position_id": r["id"],
            "asset": r["asset"],
            "direction": r["direction"],
            "price": r["entry_price"],
            "size_usd": r["size_usd"],
            "pnl": r["pnl"],
            "status": r["status"],
            "timestamp": _parse_dt(r["closed_at"]),
        })

    return sorted(events, key=lambda e: e["timestamp"])


# ── Row converters ────────────────────────────────────────────────────────────

def _row_to_signal(r: dict) -> Signal:
    return Signal(
        id=r["id"], market_id=r["market_id"], market_question=r["market_question"],
        current_price=r["current_price"], price_change_pct=r["price_change_pct"],
        timeframe_minutes=r["timeframe_minutes"], category=r["category"] or "",
        detected_at=_parse_dt(r["detected_at"]),
    )


def _row_to_analysis(r: dict) -> Analysis:
    return Analysis(
        id=r["id"], signal_id=r["signal_id"], reasoning=r["reasoning"],
        conviction_score=r["conviction_score"],
        suggested_direction=Direction(r["suggested_direction"]),
        suggested_asset=r["suggested_asset"], suggested_size_usd=r["suggested_size_usd"],
        risk_notes=r["risk_notes"] or "", created_at=_parse_dt(r["created_at"]),
    )


def _row_to_position(r: dict) -> Position:
    return Position(
        id=r["id"], analysis_id=r["analysis_id"], asset=r["asset"],
        direction=Direction(r["direction"]), entry_price=r["entry_price"],
        size_usd=r["size_usd"], leverage=r["leverage"],
        stop_loss=r["stop_loss"], take_profit=r["take_profit"],
        status=PositionStatus(r["status"]), pnl=r["pnl"] or 0.0,
        opened_at=_parse_dt(r["opened_at"]),
        closed_at=_parse_dt(r["closed_at"]),
    )


def _row_to_decision(r: dict) -> AgentDecision:
    return AgentDecision(
        id=r["id"], cycle_id=r["cycle_id"], signals_detected=r["signals_detected"] or 0,
        analyses_produced=r["analyses_produced"] or 0,
        trades_executed=r["trades_executed"] or 0,
        reasoning_summary=r["reasoning_summary"] or "",
        timestamp=_parse_dt(r["timestamp"]),
    )


def _row_to_kol_signal(r: dict) -> KolSignal:
    return KolSignal(
        id=r["id"], kol_name=r["kol_name"], wallet_address=r["wallet_address"],
        asset=r["asset"], direction=Direction(r["direction"]),
        trade_size_usd=r["trade_size_usd"],
        detected_at=_parse_dt(r["detected_at"]),
    )


def _row_to_wallet_snapshot(r: dict) -> WalletSnapshot:
    return WalletSnapshot(
        id=r["id"], balance=r["balance"], total_pnl=r["total_pnl"],
        open_positions=r["open_positions"],
        timestamp=_parse_dt(r["timestamp"]),
    )


def _row_to_position_snapshot(r: dict) -> PositionSnapshot:
    return PositionSnapshot(
        id=r["id"], position_id=r["position_id"], asset=r["asset"],
        current_price=r["current_price"], unrealized_pnl=r["unrealized_pnl"],
        timestamp=_parse_dt(r["timestamp"]),
    )
