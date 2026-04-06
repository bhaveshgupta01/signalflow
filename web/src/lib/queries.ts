import { supabase } from "./supabase";
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

function cutoff(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

// ── Signals ──────────────────────────────────────────────────────────────────

export async function getRecentSignals(
  minutes: number = 30
): Promise<Signal[]> {
  const { data } = await supabase
    .from("signals")
    .select("*")
    .gte("detected_at", cutoff(minutes))
    .order("detected_at", { ascending: false });
  return data ?? [];
}

// ── Analyses ─────────────────────────────────────────────────────────────────

export async function getRecentAnalyses(
  limit: number = 20
): Promise<Analysis[]> {
  const { data } = await supabase
    .from("analyses")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(limit);
  return data ?? [];
}

// ── Positions ────────────────────────────────────────────────────────────────

export async function getOpenPositions(): Promise<Position[]> {
  const { data } = await supabase
    .from("positions")
    .select("*")
    .eq("status", "open")
    .order("opened_at", { ascending: false });
  return data ?? [];
}

export async function getAllPositions(limit: number = 50): Promise<Position[]> {
  const { data } = await supabase
    .from("positions")
    .select("*")
    .order("opened_at", { ascending: false })
    .limit(limit);
  return data ?? [];
}

// ── Stats ────────────────────────────────────────────────────────────────────

export async function getStats(): Promise<TradingStats> {
  const { data } = await supabase.rpc("get_trading_stats");
  return (
    data ?? {
      total_trades: 0,
      closed_trades: 0,
      wins: 0,
      win_rate: 0,
      total_pnl: 0,
      open_exposure: 0,
    }
  );
}

// ── Decisions ────────────────────────────────────────────────────────────────

export async function getRecentDecisions(
  limit: number = 20
): Promise<AgentDecision[]> {
  const { data } = await supabase
    .from("agent_decisions")
    .select("*")
    .order("timestamp", { ascending: false })
    .limit(limit);
  return data ?? [];
}

// ── KOL Signals ──────────────────────────────────────────────────────────────

export async function getAllKolSignals(
  limit: number = 50
): Promise<KolSignal[]> {
  const { data } = await supabase
    .from("kol_signals")
    .select("*")
    .order("detected_at", { ascending: false })
    .limit(limit);
  return data ?? [];
}

// ── Wallet History ───────────────────────────────────────────────────────────

export async function getWalletHistory(
  limit: number = 500
): Promise<WalletSnapshot[]> {
  const { data } = await supabase
    .from("wallet_snapshots")
    .select("*")
    .order("timestamp", { ascending: false })
    .limit(limit);
  return data ?? [];
}

// ── Position Snapshots ───────────────────────────────────────────────────────

export async function getPositionSnapshots(
  positionId?: number,
  minutes: number = 1440
): Promise<PositionSnapshot[]> {
  let query = supabase
    .from("position_snapshots")
    .select("*")
    .gte("timestamp", cutoff(minutes));
  if (positionId) {
    query = query.eq("position_id", positionId);
  }
  const { data } = await query.order("timestamp", { ascending: true });
  return data ?? [];
}

// ── Trade Events ─────────────────────────────────────────────────────────────

export async function getTradeEvents(
  minutes: number = 999999
): Promise<TradeEvent[]> {
  const c = cutoff(minutes);
  const events: TradeEvent[] = [];

  // Open events
  const { data: opens } = await supabase
    .from("positions")
    .select("id, asset, direction, entry_price, size_usd, leverage, opened_at")
    .gte("opened_at", c)
    .order("opened_at", { ascending: true });
  for (const r of opens ?? []) {
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

  // Close events
  const { data: closes } = await supabase
    .from("positions")
    .select("id, asset, direction, entry_price, size_usd, pnl, status, closed_at")
    .not("closed_at", "is", null)
    .gte("closed_at", c)
    .order("closed_at", { ascending: true });
  for (const r of closes ?? []) {
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

  return events.sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );
}
