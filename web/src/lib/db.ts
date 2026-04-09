import Database from "better-sqlite3";
import path from "path";

const DB_PATH = path.resolve(process.cwd(), "..", "signalflow.db");

let _db: Database.Database | null = null;

function getDb(): Database.Database {
  if (!_db) {
    _db = new Database(DB_PATH, { readonly: true });
    _db.pragma("journal_mode = WAL");
  }
  return _db;
}

function cutoff(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

// ── Signals ────────────────────────────────────────────────────────────────────

export function getRecentSignals(minutes: number = 30) {
  const db = getDb();
  return db
    .prepare("SELECT * FROM signals WHERE detected_at >= ? ORDER BY detected_at DESC")
    .all(cutoff(minutes));
}

// ── Analyses ───────────────────────────────────────────────────────────────────

export function getRecentAnalyses(limit: number = 20) {
  const db = getDb();
  return db
    .prepare("SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?")
    .all(limit);
}

// ── Positions ──────────────────────────────────────────────────────────────────

export function getOpenPositions() {
  const db = getDb();
  return db
    .prepare("SELECT * FROM positions WHERE status = 'open' ORDER BY opened_at DESC")
    .all();
}

export function getAllPositions(limit: number = 50) {
  const db = getDb();
  return db
    .prepare("SELECT * FROM positions ORDER BY opened_at DESC LIMIT ?")
    .all(limit);
}

// ── Stats ──────────────────────────────────────────────────────────────────────

export function getStats() {
  const db = getDb();
  const total = (db.prepare("SELECT COUNT(*) as c FROM positions").get() as { c: number }).c;
  const wins = (db.prepare("SELECT COUNT(*) as c FROM positions WHERE pnl > 0 AND status != 'open'").get() as { c: number }).c;
  const closed = (db.prepare("SELECT COUNT(*) as c FROM positions WHERE status != 'open'").get() as { c: number }).c;
  const totalPnl = (db.prepare("SELECT COALESCE(SUM(pnl), 0) as s FROM positions").get() as { s: number }).s;
  const openExposure = (db.prepare("SELECT COALESCE(SUM(size_usd), 0) as s FROM positions WHERE status = 'open'").get() as { s: number }).s;
  return {
    total_trades: total,
    closed_trades: closed,
    wins,
    win_rate: closed > 0 ? (wins / closed) * 100 : 0,
    total_pnl: totalPnl,
    open_exposure: openExposure,
  };
}

// ── Decisions ──────────────────────────────────────────────────────────────────

export function getRecentDecisions(limit: number = 20) {
  const db = getDb();
  return db
    .prepare("SELECT * FROM agent_decisions ORDER BY timestamp DESC LIMIT ?")
    .all(limit);
}

// ── KOL Signals ────────────────────────────────────────────────────────────────

export function getAllKolSignals(limit: number = 50) {
  const db = getDb();
  return db
    .prepare("SELECT * FROM kol_signals ORDER BY detected_at DESC LIMIT ?")
    .all(limit);
}

// ── Wallet History ─────────────────────────────────────────────────────────────

export function getWalletHistory(limit: number = 500) {
  const db = getDb();
  return db
    .prepare("SELECT * FROM wallet_snapshots ORDER BY timestamp DESC LIMIT ?")
    .all(limit);
}

// ── Position Snapshots ─────────────────────────────────────────────────────────

export function getPositionSnapshots(positionId?: number, minutes: number = 1440) {
  const db = getDb();
  if (positionId) {
    return db
      .prepare("SELECT * FROM position_snapshots WHERE position_id = ? AND timestamp >= ? ORDER BY timestamp")
      .all(positionId, cutoff(minutes));
  }
  return db
    .prepare("SELECT * FROM position_snapshots WHERE timestamp >= ? ORDER BY timestamp")
    .all(cutoff(minutes));
}

// ── Trade Events ───────────────────────────────────────────────────────────────

export function getTradeEvents(minutes: number = 999999) {
  const db = getDb();
  const c = cutoff(minutes);
  const events: Record<string, unknown>[] = [];

  const opens = db
    .prepare("SELECT id, asset, direction, entry_price, size_usd, leverage, opened_at FROM positions WHERE opened_at >= ? ORDER BY opened_at")
    .all(c) as { id: number; asset: string; direction: string; entry_price: number; size_usd: number; leverage: number; opened_at: string }[];

  for (const r of opens) {
    events.push({
      type: "open",
      position_id: r.id,
      asset: r.asset,
      direction: r.direction,
      price: r.entry_price,
      size_usd: r.size_usd,
      leverage: r.leverage,
      timestamp: r.opened_at,
    });
  }

  const closes = db
    .prepare("SELECT id, asset, direction, entry_price, size_usd, pnl, status, closed_at FROM positions WHERE closed_at IS NOT NULL AND closed_at >= ? ORDER BY closed_at")
    .all(c) as { id: number; asset: string; direction: string; entry_price: number; size_usd: number; pnl: number; status: string; closed_at: string }[];

  for (const r of closes) {
    events.push({
      type: "close",
      position_id: r.id,
      asset: r.asset,
      direction: r.direction,
      price: r.entry_price,
      size_usd: r.size_usd,
      pnl: r.pnl,
      status: r.status,
      timestamp: r.closed_at,
    });
  }

  return events.sort((a, b) =>
    new Date(a.timestamp as string).getTime() - new Date(b.timestamp as string).getTime()
  );
}
