import type {
  Signal,
  Analysis,
  Position,
  PositionSnapshot,
  WalletSnapshot,
  KolSignal,
  AgentDecision,
  TradingStats,
  TradeEvent,
} from "./types";

const API = "/api/data";

async function query<T>(params: Record<string, string | number>): Promise<T> {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    sp.set(k, String(v));
  }
  const res = await fetch(`${API}?${sp.toString()}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ── Signals ──────────────────────────────────────────────────────────────────

export async function getRecentSignals(minutes: number = 30): Promise<Signal[]> {
  return query({ q: "signals", minutes });
}

// ── Analyses ─────────────────────────────────────────────────────────────────

export async function getRecentAnalyses(limit: number = 20): Promise<Analysis[]> {
  return query({ q: "analyses", limit });
}

// ── Positions ────────────────────────────────────────────────────────────────

export async function getOpenPositions(): Promise<Position[]> {
  return query({ q: "positions_open" });
}

export async function getAllPositions(limit: number = 50): Promise<Position[]> {
  return query({ q: "positions_all", limit });
}

// ── Stats ────────────────────────────────────────────────────────────────────

export async function getStats(): Promise<TradingStats> {
  return query({ q: "stats" });
}

// ── Decisions ────────────────────────────────────────────────────────────────

export async function getRecentDecisions(limit: number = 20): Promise<AgentDecision[]> {
  return query({ q: "decisions", limit });
}

// ── KOL Signals ──────────────────────────────────────────────────────────────

export async function getAllKolSignals(limit: number = 50): Promise<KolSignal[]> {
  return query({ q: "kol_signals", limit });
}

// ── Wallet History ───────────────────────────────────────────────────────────

export async function getWalletHistory(limit: number = 500): Promise<WalletSnapshot[]> {
  return query({ q: "wallet_history", limit });
}

// ── Position Snapshots ───────────────────────────────────────────────────────

export async function getPositionSnapshots(
  positionId?: number,
  minutes: number = 1440
): Promise<PositionSnapshot[]> {
  const params: Record<string, string | number> = { q: "position_snapshots", minutes };
  if (positionId) params.position_id = positionId;
  return query(params);
}

// ── Trade Events ─────────────────────────────────────────────────────────────

export async function getTradeEvents(minutes: number = 999999): Promise<TradeEvent[]> {
  return query({ q: "trade_events", minutes });
}
