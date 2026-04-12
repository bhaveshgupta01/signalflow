"""SQLite persistence layer for SignalFlow."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Optional

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
from config import DB_PATH

_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db() -> None:
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id       TEXT NOT NULL,
            market_question TEXT NOT NULL,
            current_price   REAL NOT NULL,
            price_change_pct REAL NOT NULL,
            timeframe_minutes INTEGER NOT NULL,
            category        TEXT DEFAULT '',
            detected_at     TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id           INTEGER NOT NULL REFERENCES signals(id),
            reasoning           TEXT NOT NULL,
            conviction_score    REAL NOT NULL,
            suggested_direction TEXT NOT NULL,
            suggested_asset     TEXT NOT NULL,
            suggested_size_usd  REAL NOT NULL,
            risk_notes          TEXT DEFAULT '',
            created_at          TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS positions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id   INTEGER NOT NULL REFERENCES analyses(id),
            asset         TEXT NOT NULL,
            direction     TEXT NOT NULL,
            entry_price   REAL NOT NULL,
            size_usd      REAL NOT NULL,
            leverage      INTEGER NOT NULL,
            stop_loss     REAL NOT NULL,
            take_profit   REAL NOT NULL,
            status        TEXT NOT NULL DEFAULT 'open',
            pnl           REAL DEFAULT 0.0,
            opened_at     TEXT NOT NULL,
            closed_at     TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_decisions (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_id          TEXT NOT NULL,
            signals_detected  INTEGER DEFAULT 0,
            analyses_produced INTEGER DEFAULT 0,
            trades_executed   INTEGER DEFAULT 0,
            reasoning_summary TEXT DEFAULT '',
            timestamp         TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kol_signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            kol_name        TEXT NOT NULL,
            wallet_address  TEXT NOT NULL,
            asset           TEXT NOT NULL,
            direction       TEXT NOT NULL,
            trade_size_usd  REAL NOT NULL,
            detected_at     TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS wallet_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            balance         REAL NOT NULL,
            total_pnl       REAL NOT NULL,
            open_positions  INTEGER NOT NULL,
            timestamp       TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS position_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            position_id     INTEGER NOT NULL REFERENCES positions(id),
            asset           TEXT NOT NULL,
            current_price   REAL NOT NULL,
            unrealized_pnl  REAL NOT NULL,
            timestamp       TEXT NOT NULL
        );

        -- v2: per-trade signal attribution so we can measure which edge actually pays
        CREATE TABLE IF NOT EXISTS signal_attribution (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            position_id      INTEGER NOT NULL REFERENCES positions(id),
            score_funding    REAL DEFAULT 0.0,
            score_polymarket REAL DEFAULT 0.0,
            score_kol        REAL DEFAULT 0.0,
            score_trend      REAL DEFAULT 0.0,
            score_total      REAL DEFAULT 0.0,
            direction        TEXT NOT NULL,
            notes            TEXT DEFAULT '',
            created_at       TEXT NOT NULL
        );


        CREATE INDEX IF NOT EXISTS idx_analyses_signal_id ON analyses(signal_id);
        CREATE INDEX IF NOT EXISTS idx_signal_attribution_position_id ON signal_attribution(position_id);
        CREATE INDEX IF NOT EXISTS idx_positions_analysis_id ON positions(analysis_id);
        CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
        CREATE INDEX IF NOT EXISTS idx_position_snapshots_position_id ON position_snapshots(position_id);
        CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_timestamp ON wallet_snapshots(timestamp);
        CREATE INDEX IF NOT EXISTS idx_signals_detected_at ON signals(detected_at);
        CREATE INDEX IF NOT EXISTS idx_kol_signals_detected_at ON kol_signals(detected_at);
    """)

    # v2 ALTERs (idempotent — guarded by PRAGMA check)
    existing_cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(positions)").fetchall()
    }
    if "extreme_price" not in existing_cols:
        conn.execute("ALTER TABLE positions ADD COLUMN extreme_price REAL")
    if "atr_at_entry" not in existing_cols:
        conn.execute("ALTER TABLE positions ADD COLUMN atr_at_entry REAL")
    conn.commit()


# ── Signals ───────────────────────────────────────────────────────────────────

def save_signal(s: Signal) -> Signal:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO signals
           (market_id, market_question, current_price, price_change_pct,
            timeframe_minutes, category, detected_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (s.market_id, s.market_question, s.current_price, s.price_change_pct,
         s.timeframe_minutes, s.category, s.detected_at.isoformat()),
    )
    conn.commit()
    s.id = cur.lastrowid
    return s


def get_recent_signals(minutes: int = 30) -> list[Signal]:
    conn = _get_conn()
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    rows = conn.execute(
        "SELECT * FROM signals WHERE detected_at >= ? ORDER BY detected_at DESC", (cutoff,)
    ).fetchall()
    return [_row_to_signal(r) for r in rows]


def get_signals_for_market(market_id: str, minutes: int = 30) -> list[Signal]:
    conn = _get_conn()
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    rows = conn.execute(
        "SELECT * FROM signals WHERE market_id = ? AND detected_at >= ? ORDER BY detected_at DESC",
        (market_id, cutoff),
    ).fetchall()
    return [_row_to_signal(r) for r in rows]


# ── Analyses ──────────────────────────────────────────────────────────────────

def save_analysis(a: Analysis) -> Analysis:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO analyses
           (signal_id, reasoning, conviction_score, suggested_direction,
            suggested_asset, suggested_size_usd, risk_notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (a.signal_id, a.reasoning, a.conviction_score, a.suggested_direction.value,
         a.suggested_asset, a.suggested_size_usd, a.risk_notes, a.created_at.isoformat()),
    )
    conn.commit()
    a.id = cur.lastrowid
    return a


def get_recent_analyses(limit: int = 20) -> list[Analysis]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_row_to_analysis(r) for r in rows]


# ── Positions ─────────────────────────────────────────────────────────────────

def save_position(p: Position) -> Position:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO positions
           (analysis_id, asset, direction, entry_price, size_usd, leverage,
            stop_loss, take_profit, status, pnl, opened_at, closed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (p.analysis_id, p.asset, p.direction.value, p.entry_price, p.size_usd,
         p.leverage, p.stop_loss, p.take_profit, p.status.value, p.pnl,
         p.opened_at.isoformat(), p.closed_at.isoformat() if p.closed_at else None),
    )
    conn.commit()
    p.id = cur.lastrowid
    return p


def update_position(position_id: int, *, status: Optional[PositionStatus] = None,
                     pnl: Optional[float] = None, closed_at: Optional[datetime] = None,
                     stop_loss: Optional[float] = None,
                     extreme_price: Optional[float] = None,
                     atr_at_entry: Optional[float] = None) -> None:
    conn = _get_conn()
    updates: list[str] = []
    params: list = []
    if status is not None:
        updates.append("status = ?")
        params.append(status.value)
    if pnl is not None:
        updates.append("pnl = ?")
        params.append(pnl)
    if closed_at is not None:
        updates.append("closed_at = ?")
        params.append(closed_at.isoformat())
    if stop_loss is not None:
        updates.append("stop_loss = ?")
        params.append(stop_loss)
    if extreme_price is not None:
        updates.append("extreme_price = ?")
        params.append(extreme_price)
    if atr_at_entry is not None:
        updates.append("atr_at_entry = ?")
        params.append(atr_at_entry)
    if not updates:
        return
    params.append(position_id)
    conn.execute(f"UPDATE positions SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()


def get_position_extra(position_id: int) -> dict:
    """Return v2-only fields for a position (extreme_price, atr_at_entry)."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT extreme_price, atr_at_entry FROM positions WHERE id = ?",
        (position_id,),
    ).fetchone()
    if not row:
        return {"extreme_price": None, "atr_at_entry": None}
    return {
        "extreme_price": row["extreme_price"],
        "atr_at_entry": row["atr_at_entry"],
    }


# ── Signal Attribution (v2) ──────────────────────────────────────────────────

def save_signal_attribution(
    position_id: int,
    *,
    score_funding: float = 0.0,
    score_polymarket: float = 0.0,
    score_kol: float = 0.0,
    score_trend: float = 0.0,
    score_total: float = 0.0,
    direction: str = "long",
    notes: str = "",
) -> None:
    conn = _get_conn()
    conn.execute(
        """INSERT INTO signal_attribution
           (position_id, score_funding, score_polymarket, score_kol,
            score_trend, score_total, direction, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (position_id, score_funding, score_polymarket, score_kol,
         score_trend, score_total, direction, notes,
         datetime.utcnow().isoformat()),
    )
    conn.commit()


def get_attribution_summary(days: int = 7) -> dict:
    """Return per-source PnL contribution over the last N days.

    For each closed position with attribution, we compute the proportion of
    score that came from each source and multiply by the realized PnL.
    """
    conn = _get_conn()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT sa.score_funding, sa.score_polymarket, sa.score_kol,
                  sa.score_trend, sa.score_total, p.pnl
           FROM signal_attribution sa
           JOIN positions p ON p.id = sa.position_id
           WHERE p.status != 'open' AND p.opened_at >= ?""",
        (cutoff,),
    ).fetchall()
    out = {"funding": 0.0, "polymarket": 0.0, "kol": 0.0, "trend": 0.0, "trades": 0}
    for r in rows:
        total = abs(r["score_total"]) or 1.0
        out["funding"] += abs(r["score_funding"]) / total * r["pnl"]
        out["polymarket"] += abs(r["score_polymarket"]) / total * r["pnl"]
        out["kol"] += abs(r["score_kol"]) / total * r["pnl"]
        out["trend"] += abs(r["score_trend"]) / total * r["pnl"]
        out["trades"] += 1
    return out


def get_open_positions() -> list[Position]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM positions WHERE status = 'open' ORDER BY opened_at DESC"
    ).fetchall()
    return [_row_to_position(r) for r in rows]


def get_last_trade_time() -> datetime | None:
    """Return the opened_at of the most recent position, or None if no trades."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT opened_at FROM positions ORDER BY opened_at DESC LIMIT 1"
    ).fetchone()
    if row:
        return datetime.fromisoformat(row["opened_at"])
    return None


def get_all_positions(limit: int = 50) -> list[Position]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM positions ORDER BY opened_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_row_to_position(r) for r in rows]


# ── Agent Decisions ───────────────────────────────────────────────────────────

def save_decision(d: AgentDecision) -> AgentDecision:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO agent_decisions
           (cycle_id, signals_detected, analyses_produced, trades_executed,
            reasoning_summary, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (d.cycle_id, d.signals_detected, d.analyses_produced, d.trades_executed,
         d.reasoning_summary, d.timestamp.isoformat()),
    )
    conn.commit()
    d.id = cur.lastrowid
    return d


def get_recent_decisions(limit: int = 20) -> list[AgentDecision]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM agent_decisions ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_row_to_decision(r) for r in rows]


# ── KOL Signals ──────────────────────────────────────────────────────────────

def save_kol_signal(k: KolSignal) -> KolSignal:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO kol_signals
           (kol_name, wallet_address, asset, direction, trade_size_usd, detected_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (k.kol_name, k.wallet_address, k.asset, k.direction.value,
         k.trade_size_usd, k.detected_at.isoformat()),
    )
    conn.commit()
    k.id = cur.lastrowid
    return k


def get_recent_kol_signals(minutes: int = 60) -> list[KolSignal]:
    conn = _get_conn()
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    rows = conn.execute(
        "SELECT * FROM kol_signals WHERE detected_at >= ? ORDER BY detected_at DESC",
        (cutoff,),
    ).fetchall()
    return [_row_to_kol_signal(r) for r in rows]


def get_kol_signals_for_asset(asset: str, minutes: int = 60) -> list[KolSignal]:
    conn = _get_conn()
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    rows = conn.execute(
        "SELECT * FROM kol_signals WHERE UPPER(asset) = ? AND detected_at >= ? ORDER BY detected_at DESC",
        (asset.upper(), cutoff),
    ).fetchall()
    return [_row_to_kol_signal(r) for r in rows]


def get_all_kol_signals(limit: int = 50) -> list[KolSignal]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM kol_signals ORDER BY detected_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_row_to_kol_signal(r) for r in rows]


# ── Position Snapshots ────────────────────────────────────────────────────────

def save_position_snapshot(ps: PositionSnapshot) -> PositionSnapshot:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO position_snapshots
           (position_id, asset, current_price, unrealized_pnl, timestamp)
           VALUES (?, ?, ?, ?, ?)""",
        (ps.position_id, ps.asset, ps.current_price, ps.unrealized_pnl,
         ps.timestamp.isoformat()),
    )
    conn.commit()
    ps.id = cur.lastrowid
    return ps


def get_position_snapshots(position_id: int | None = None, minutes: int = 1440) -> list[PositionSnapshot]:
    conn = _get_conn()
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    if position_id:
        rows = conn.execute(
            "SELECT * FROM position_snapshots WHERE position_id = ? AND timestamp >= ? ORDER BY timestamp",
            (position_id, cutoff),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM position_snapshots WHERE timestamp >= ? ORDER BY timestamp",
            (cutoff,),
        ).fetchall()
    return [_row_to_position_snapshot(r) for r in rows]


def get_asset_pnl_history(minutes: int = 1440) -> dict[str, list[tuple]]:
    """Return {asset: [(timestamp, sum_pnl), ...]} for charting."""
    conn = _get_conn()
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    rows = conn.execute(
        """SELECT asset, timestamp, SUM(unrealized_pnl) as total_pnl
           FROM position_snapshots
           WHERE timestamp >= ?
           GROUP BY asset, timestamp
           ORDER BY timestamp""",
        (cutoff,),
    ).fetchall()
    result: dict[str, list[tuple]] = {}
    for r in rows:
        asset = r["asset"]
        if asset not in result:
            result[asset] = []
        result[asset].append((datetime.fromisoformat(r["timestamp"]), r["total_pnl"]))
    return result


# ── Wallet Snapshots ─────────────────────────────────────────────────────────

def save_wallet_snapshot(ws: WalletSnapshot) -> WalletSnapshot:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO wallet_snapshots
           (balance, total_pnl, open_positions, timestamp)
           VALUES (?, ?, ?, ?)""",
        (ws.balance, ws.total_pnl, ws.open_positions, ws.timestamp.isoformat()),
    )
    conn.commit()
    ws.id = cur.lastrowid
    return ws


def get_wallet_history(limit: int = 100) -> list[WalletSnapshot]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM wallet_snapshots ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_row_to_wallet_snapshot(r) for r in rows]


# ── Aggregate Stats ───────────────────────────────────────────────────────────

def get_stats() -> dict:
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    wins = conn.execute("SELECT COUNT(*) FROM positions WHERE pnl > 0 AND status != 'open'").fetchone()[0]
    closed = conn.execute("SELECT COUNT(*) FROM positions WHERE status != 'open'").fetchone()[0]
    total_pnl = conn.execute("SELECT COALESCE(SUM(pnl), 0) FROM positions").fetchone()[0]
    open_exposure = conn.execute(
        "SELECT COALESCE(SUM(size_usd), 0) FROM positions WHERE status = 'open'"
    ).fetchone()[0]
    return {
        "total_trades": total,
        "closed_trades": closed,
        "wins": wins,
        "win_rate": (wins / closed * 100) if closed > 0 else 0.0,
        "total_pnl": total_pnl,
        "open_exposure": open_exposure,
    }


def get_performance_context(asset: str, direction: str, days: int = 7) -> dict:
    """Return historical performance for similar trades — used for AI learning loop.

    Returns counts and PnL stats for:
      - Same asset + same direction (most specific)
      - Same asset (any direction)
      - Same direction (any asset)
      - All trades in the period
    Plus the 3 most recent similar trades with their AI reasoning for context.
    """
    conn = _get_conn()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    asset_u = asset.upper()
    dir_l = direction.lower()

    def _stats(query: str, params: tuple) -> dict:
        rows = conn.execute(query, params).fetchall()
        if not rows:
            return {"trades": 0, "wins": 0, "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0}
        wins = sum(1 for r in rows if r["pnl"] > 0)
        total_pnl = sum(r["pnl"] for r in rows)
        return {
            "trades": len(rows),
            "wins": wins,
            "win_rate": round(wins / len(rows) * 100, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(total_pnl / len(rows), 3),
        }

    # Same asset + direction (most relevant)
    exact = _stats(
        "SELECT pnl FROM positions WHERE UPPER(asset)=? AND direction=? "
        "AND status!='open' AND opened_at >= ?",
        (asset_u, dir_l, cutoff),
    )
    # Same asset
    same_asset = _stats(
        "SELECT pnl FROM positions WHERE UPPER(asset)=? AND status!='open' AND opened_at >= ?",
        (asset_u, cutoff),
    )
    # Same direction
    same_dir = _stats(
        "SELECT pnl FROM positions WHERE direction=? AND status!='open' AND opened_at >= ?",
        (dir_l, cutoff),
    )
    # All trades in period
    overall = _stats(
        "SELECT pnl FROM positions WHERE status!='open' AND opened_at >= ?",
        (cutoff,),
    )

    # Recent similar trades with reasoning (most useful for AI to learn from)
    recent_rows = conn.execute(
        """SELECT p.asset, p.direction, p.pnl, p.status, p.opened_at,
                  a.reasoning, a.conviction_score, a.risk_notes
           FROM positions p
           LEFT JOIN analyses a ON a.id = p.analysis_id
           WHERE UPPER(p.asset)=? AND p.direction=? AND p.status!='open'
             AND p.opened_at >= ?
           ORDER BY p.opened_at DESC LIMIT 3""",
        (asset_u, dir_l, cutoff),
    ).fetchall()
    recent = [
        {
            "pnl": round(r["pnl"], 2),
            "status": r["status"],
            "conviction": round(r["conviction_score"] or 0, 2),
            "reasoning": (r["reasoning"] or "")[:200],
        }
        for r in recent_rows
    ]

    return {
        "exact_match": exact,       # same asset + same direction
        "same_asset": same_asset,   # same asset only
        "same_direction": same_dir, # same direction only
        "overall": overall,         # all trades
        "recent_similar": recent,   # last 3 trades with reasoning
    }


# ── Trade Events (for chart annotations) ────────────────────────────────────

def get_trade_events(minutes: int = 999999) -> list[dict]:
    """Return trade open/close events for chart annotations."""
    conn = _get_conn()
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    events = []

    # Open events
    rows = conn.execute(
        "SELECT id, asset, direction, entry_price, size_usd, leverage, opened_at "
        "FROM positions WHERE opened_at >= ? ORDER BY opened_at",
        (cutoff,),
    ).fetchall()
    for r in rows:
        events.append({
            "type": "open",
            "position_id": r["id"],
            "asset": r["asset"],
            "direction": r["direction"],
            "price": r["entry_price"],
            "size_usd": r["size_usd"],
            "leverage": r["leverage"],
            "timestamp": datetime.fromisoformat(r["opened_at"]),
        })

    # Close events
    rows = conn.execute(
        "SELECT id, asset, direction, entry_price, size_usd, pnl, status, closed_at "
        "FROM positions WHERE closed_at IS NOT NULL AND closed_at >= ? ORDER BY closed_at",
        (cutoff,),
    ).fetchall()
    for r in rows:
        events.append({
            "type": "close",
            "position_id": r["id"],
            "asset": r["asset"],
            "direction": r["direction"],
            "price": r["entry_price"],
            "size_usd": r["size_usd"],
            "pnl": r["pnl"],
            "status": r["status"],
            "timestamp": datetime.fromisoformat(r["closed_at"]),
        })

    return sorted(events, key=lambda e: e["timestamp"])


# ── Row converters ────────────────────────────────────────────────────────────

def _row_to_signal(r: sqlite3.Row) -> Signal:
    return Signal(
        id=r["id"], market_id=r["market_id"], market_question=r["market_question"],
        current_price=r["current_price"], price_change_pct=r["price_change_pct"],
        timeframe_minutes=r["timeframe_minutes"], category=r["category"],
        detected_at=datetime.fromisoformat(r["detected_at"]),
    )


def _row_to_analysis(r: sqlite3.Row) -> Analysis:
    return Analysis(
        id=r["id"], signal_id=r["signal_id"], reasoning=r["reasoning"],
        conviction_score=r["conviction_score"],
        suggested_direction=Direction(r["suggested_direction"]),
        suggested_asset=r["suggested_asset"], suggested_size_usd=r["suggested_size_usd"],
        risk_notes=r["risk_notes"], created_at=datetime.fromisoformat(r["created_at"]),
    )


def _row_to_position(r: sqlite3.Row) -> Position:
    return Position(
        id=r["id"], analysis_id=r["analysis_id"], asset=r["asset"],
        direction=Direction(r["direction"]), entry_price=r["entry_price"],
        size_usd=r["size_usd"], leverage=r["leverage"],
        stop_loss=r["stop_loss"], take_profit=r["take_profit"],
        status=PositionStatus(r["status"]), pnl=r["pnl"],
        opened_at=datetime.fromisoformat(r["opened_at"]),
        closed_at=datetime.fromisoformat(r["closed_at"]) if r["closed_at"] else None,
    )


def _row_to_decision(r: sqlite3.Row) -> AgentDecision:
    return AgentDecision(
        id=r["id"], cycle_id=r["cycle_id"], signals_detected=r["signals_detected"],
        analyses_produced=r["analyses_produced"], trades_executed=r["trades_executed"],
        reasoning_summary=r["reasoning_summary"],
        timestamp=datetime.fromisoformat(r["timestamp"]),
    )


def _row_to_kol_signal(r: sqlite3.Row) -> KolSignal:
    return KolSignal(
        id=r["id"], kol_name=r["kol_name"], wallet_address=r["wallet_address"],
        asset=r["asset"], direction=Direction(r["direction"]),
        trade_size_usd=r["trade_size_usd"],
        detected_at=datetime.fromisoformat(r["detected_at"]),
    )


def _row_to_wallet_snapshot(r: sqlite3.Row) -> WalletSnapshot:
    return WalletSnapshot(
        id=r["id"], balance=r["balance"], total_pnl=r["total_pnl"],
        open_positions=r["open_positions"],
        timestamp=datetime.fromisoformat(r["timestamp"]),
    )


def _row_to_position_snapshot(r: sqlite3.Row) -> PositionSnapshot:
    return PositionSnapshot(
        id=r["id"], position_id=r["position_id"], asset=r["asset"],
        current_price=r["current_price"], unrealized_pnl=r["unrealized_pnl"],
        timestamp=datetime.fromisoformat(r["timestamp"]),
    )
