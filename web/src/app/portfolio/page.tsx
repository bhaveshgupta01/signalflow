"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import {
  ComposedChart,
  Area,
  Line,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
  Legend,
} from "recharts";
import {
  getStats,
  getWalletHistory,
  getAllPositions,
  getOpenPositions,
  getRecentAnalyses,
  getPositionSnapshots,
  getTradeEvents,
} from "@/lib/queries";
import { COLORS, getAssetColor } from "@/lib/colors";
import type {
  TradingStats,
  WalletSnapshot,
  Position,
  Analysis,
  PositionSnapshot,
  TradeEvent,
} from "@/lib/types";

/* ─── Constants ────────────────────────────────────────────────────────────── */

const SORA: React.CSSProperties = { fontFamily: "'Sora', sans-serif" };
const INTER: React.CSSProperties = { fontFamily: "'Inter', sans-serif" };
const STARTING_BALANCE = 100;

const TIME_RANGES = [
  { value: 60, label: "1H" },
  { value: 360, label: "6H" },
  { value: 1440, label: "1D" },
  { value: 0, label: "ALL" },
];

/* ─── Helpers ──────────────────────────────────────────────────────────────── */

function fmtUsd(n: number, decimals = 2): string {
  const sign = n >= 0 ? "" : "-";
  return `${sign}$${Math.abs(n).toFixed(decimals)}`;
}

function fmtPct(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

function pnlColor(n: number): string {
  return n >= 0 ? COLORS.up : COLORS.down;
}

function pnlClass(n: number): string {
  return n >= 0 ? "text-[#84f593]" : "text-[#f2685f]";
}

function convictionBadge(score: number) {
  if (score >= 0.7) return "bg-[#bfa1f5]/10 text-[#bfa1f5]";
  if (score >= 0.4) return "bg-[#F59E0B]/10 text-[#F59E0B]";
  return "bg-[#858189]/10 text-[#858189]";
}

function durationStr(ms: number): string {
  if (ms < 0) return "-";
  const mins = Math.round(ms / 60_000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  const rm = mins % 60;
  if (hrs < 24) return `${hrs}h ${rm}m`;
  const days = Math.floor(hrs / 24);
  return `${days}d ${hrs % 24}h`;
}

function timeAgo(dateStr: string) {
  const mins = Math.round((Date.now() - new Date(dateStr).getTime()) / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

function fmtTime(ts: string): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function fmtDateTime(ts: string): string {
  return new Date(ts).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/* ─── Custom Scatter Shapes ────────────────────────────────────────────────── */

function BuyMarker(props: any) {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  return (
    <polygon
      points={`${cx},${cy - 8} ${cx - 7},${cy + 5} ${cx + 7},${cy + 5}`}
      fill={COLORS.up}
      stroke={COLORS.bg}
      strokeWidth={1.5}
    />
  );
}

function SellMarker(props: any) {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  return (
    <polygon
      points={`${cx},${cy + 8} ${cx - 7},${cy - 5} ${cx + 7},${cy - 5}`}
      fill={COLORS.down}
      stroke={COLORS.bg}
      strokeWidth={1.5}
    />
  );
}

/* ─── Custom Tooltip ───────────────────────────────────────────────────────── */

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl border px-3 py-2 text-xs shadow-xl"
      style={{
        background: COLORS.card,
        borderColor: COLORS.borderBold,
        ...INTER,
      }}
    >
      <div className="text-[#858189] mb-1">{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className="flex items-center gap-2 py-0.5">
          <span
            className="w-2 h-2 rounded-full inline-block"
            style={{ background: p.color || p.stroke }}
          />
          <span className="text-[#b8b5bb]">{p.name}:</span>
          <span className="text-white font-medium tabular-nums">
            ${Number(p.value).toFixed(2)}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ─── Risk Metrics Computation ─────────────────────────────────────────────── */

interface RiskMetrics {
  profitFactor: number | null;
  maxDrawdownPct: number;
  avgDuration: string;
  bestTrade: number;
  worstTrade: number;
  sharpe: number | null;
}

function computeRiskMetrics(
  positions: Position[],
  wallet: WalletSnapshot[]
): RiskMetrics {
  const closed = positions.filter((p) => p.status !== "open");

  // Profit factor
  let grossWins = 0;
  let grossLosses = 0;
  const pnls: number[] = [];
  let bestTrade = 0;
  let worstTrade = 0;

  for (const p of closed) {
    pnls.push(p.pnl);
    if (p.pnl >= 0) grossWins += p.pnl;
    else grossLosses += Math.abs(p.pnl);
    if (p.pnl > bestTrade) bestTrade = p.pnl;
    if (p.pnl < worstTrade) worstTrade = p.pnl;
  }

  const profitFactor = grossLosses > 0 ? grossWins / grossLosses : closed.length > 0 ? Infinity : null;

  // Max drawdown from wallet history
  let peak = 0;
  let maxDd = 0;
  const sorted = [...wallet].reverse();
  for (const w of sorted) {
    if (w.balance > peak) peak = w.balance;
    const dd = peak > 0 ? (peak - w.balance) / peak : 0;
    if (dd > maxDd) maxDd = dd;
  }

  // Average trade duration
  let totalDur = 0;
  let durCount = 0;
  for (const p of closed) {
    if (p.closed_at && p.opened_at) {
      totalDur += new Date(p.closed_at).getTime() - new Date(p.opened_at).getTime();
      durCount++;
    }
  }

  // Sharpe-like
  let sharpe: number | null = null;
  if (pnls.length >= 3) {
    const mean = pnls.reduce((a, b) => a + b, 0) / pnls.length;
    const variance = pnls.reduce((s, v) => s + (v - mean) ** 2, 0) / pnls.length;
    const std = Math.sqrt(variance);
    if (std > 0) sharpe = mean / std;
  }

  return {
    profitFactor,
    maxDrawdownPct: maxDd * 100,
    avgDuration: durCount > 0 ? durationStr(totalDur / durCount) : "-",
    bestTrade,
    worstTrade,
    sharpe,
  };
}

/* ─── Main Page Component ──────────────────────────────────────────────────── */

export default function PortfolioPage() {
  const [stats, setStats] = useState<TradingStats | null>(null);
  const [wallet, setWallet] = useState<WalletSnapshot[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [openPos, setOpenPos] = useState<Position[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [snapshots, setSnapshots] = useState<PositionSnapshot[]>([]);
  const [tradeEvents, setTradeEvents] = useState<TradeEvent[]>([]);
  const [range, setRange] = useState(0);
  const [expandedTrade, setExpandedTrade] = useState<number | null>(null);

  const load = useCallback(async () => {
    const [s, w, p, o, a, snap, ev] = await Promise.all([
      getStats(),
      getWalletHistory(2000),
      getAllPositions(200),
      getOpenPositions(),
      getRecentAnalyses(200),
      getPositionSnapshots(undefined, 999999),
      getTradeEvents(999999),
    ]);
    setStats(s);
    setWallet(w);
    setPositions(p);
    setOpenPos(o);
    setAnalyses(a);
    setSnapshots(snap);
    setTradeEvents(ev);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, [load]);

  /* ─── Derived data ─────────────────────────────────────────────────────── */

  const pnl = stats?.total_pnl ?? 0;
  const balance = STARTING_BALANCE + pnl;
  const pnlPct = (pnl / STARTING_BALANCE) * 100;
  const losses = (stats?.closed_trades ?? 0) - (stats?.wins ?? 0);

  const analysisById = useMemo(
    () => new Map(analyses.map((a) => [a.id, a])),
    [analyses]
  );

  // Time filter
  const cutoff = range === 0 ? 0 : Date.now() - range * 60_000;
  const filteredWallet = useMemo(
    () =>
      range === 0
        ? wallet
        : wallet.filter((s) => new Date(s.timestamp).getTime() >= cutoff),
    [wallet, range, cutoff]
  );

  // Risk metrics
  const risk = useMemo(
    () => computeRiskMetrics(positions, wallet),
    [positions, wallet]
  );

  // Position map for chart legend
  const positionMap = useMemo(() => {
    const m = new Map<number, Position>();
    for (const p of positions) m.set(p.id, p);
    return m;
  }, [positions]);

  /* ─── Build merged chart data ──────────────────────────────────────────── */

  const { chartData, positionIds } = useMemo(() => {
    // Collect all timestamps from wallet + snapshots + events
    type Row = {
      ts: number;
      time: string;
      balance?: number;
      buyVal?: number;
      sellVal?: number;
      [key: string]: any;
    };

    // Build a map: ts -> row
    const rowMap = new Map<number, Row>();

    function getOrCreate(ts: number): Row {
      // Round to nearest minute for merging
      const key = Math.round(ts / 60_000) * 60_000;
      if (!rowMap.has(key)) {
        rowMap.set(key, { ts: key, time: fmtTime(new Date(key).toISOString()) });
      }
      return rowMap.get(key)!;
    }

    // Wallet balance line
    const sortedWallet = [...filteredWallet].reverse();
    for (const w of sortedWallet) {
      const ts = new Date(w.timestamp).getTime();
      if (cutoff > 0 && ts < cutoff) continue;
      const row = getOrCreate(ts);
      row.balance = Number(w.balance.toFixed(2));
    }

    // Per-position value lines from snapshots
    const posIds = new Set<number>();
    for (const s of snapshots) {
      const ts = new Date(s.timestamp).getTime();
      if (cutoff > 0 && ts < cutoff) continue;
      posIds.add(s.position_id);
      const pos = positionMap.get(s.position_id);
      if (!pos) continue;
      const margin = pos.size_usd;
      const row = getOrCreate(ts);
      const key = `pos_${s.position_id}`;
      row[key] = Number((margin + s.unrealized_pnl).toFixed(2));
    }

    // Trade events as buy/sell markers
    for (const ev of tradeEvents) {
      const ts = new Date(ev.timestamp).getTime();
      if (cutoff > 0 && ts < cutoff) continue;
      const row = getOrCreate(ts);
      if (ev.type === "open") {
        // Place marker at wallet balance or approximate
        row.buyVal = row.balance ?? STARTING_BALANCE;
      } else {
        row.sellVal = row.balance ?? STARTING_BALANCE;
      }
    }

    // Sort by timestamp
    const sorted = Array.from(rowMap.values()).sort((a, b) => a.ts - b.ts);

    // Forward-fill balance for rows that only have position data
    let lastBal: number | undefined;
    for (const row of sorted) {
      if (row.balance != null) lastBal = row.balance;
      else if (lastBal != null) row.balance = lastBal;
    }

    return { chartData: sorted, positionIds: Array.from(posIds) };
  }, [filteredWallet, snapshots, tradeEvents, positionMap, cutoff]);

  /* ─── Latest snapshots for open positions ──────────────────────────────── */

  const latestSnapshotByPos = useMemo(() => {
    const m = new Map<number, PositionSnapshot>();
    // snapshots are presumably ordered; take last per position_id
    for (const s of snapshots) {
      const existing = m.get(s.position_id);
      if (!existing || new Date(s.timestamp) > new Date(existing.timestamp)) {
        m.set(s.position_id, s);
      }
    }
    return m;
  }, [snapshots]);

  /* ─── Closed positions for trade history ───────────────────────────────── */

  const closedPositions = useMemo(
    () =>
      positions
        .filter((p) => p.status !== "open")
        .sort(
          (a, b) =>
            new Date(b.closed_at || b.opened_at).getTime() -
            new Date(a.closed_at || a.opened_at).getTime()
        )
        .slice(0, 30),
    [positions]
  );

  /* ─── Render ───────────────────────────────────────────────────────────── */

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-[1400px] mx-auto">
      {/* ────── HEADER SECTION ────── */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h1
            className="text-2xl lg:text-3xl font-bold text-white tracking-tight"
            style={SORA}
          >
            Portfolio
          </h1>
          <p className="text-sm text-[#858189] mt-1" style={INTER}>
            Live performance dashboard &middot; Auto-refreshes every 10s
          </p>
        </div>

        {/* Big balance display */}
        {stats && (
          <div className="flex items-end gap-6 flex-wrap">
            <div className="text-right">
              <div
                className="text-xs font-medium uppercase tracking-wider text-[#858189] mb-1"
                style={SORA}
              >
                Wallet Value
              </div>
              <div
                className="text-3xl lg:text-4xl font-bold text-white tabular-nums"
                style={SORA}
              >
                {fmtUsd(balance)}
              </div>
            </div>
            <div className="text-right">
              <div
                className="text-xs font-medium uppercase tracking-wider text-[#858189] mb-1"
                style={SORA}
              >
                Total PnL
              </div>
              <div
                className={`text-2xl font-bold tabular-nums ${pnlClass(pnl)}`}
                style={SORA}
              >
                {pnl >= 0 ? "+" : ""}
                {fmtUsd(pnl)} <span className="text-lg">({fmtPct(pnlPct)})</span>
              </div>
            </div>
            <div className="text-right">
              <div
                className="text-xs font-medium uppercase tracking-wider text-[#858189] mb-1"
                style={SORA}
              >
                Win Rate
              </div>
              <div
                className={`text-2xl font-bold tabular-nums ${
                  stats.win_rate >= 50 ? "text-[#84f593]" : "text-[#f2685f]"
                }`}
                style={SORA}
              >
                {stats.win_rate.toFixed(1)}%
              </div>
            </div>
            <div className="text-right">
              <div
                className="text-xs font-medium uppercase tracking-wider text-[#858189] mb-1"
                style={SORA}
              >
                Trades
              </div>
              <div className="text-lg font-semibold text-white tabular-nums" style={SORA}>
                <span className="text-[#84f593]">{stats.wins}W</span>
                {" / "}
                <span className="text-[#f2685f]">{losses}L</span>
                {" / "}
                <span className="text-[#bfa1f5]">{openPos.length}O</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ────── INVESTMENT PERFORMANCE CHART ────── */}
      <section className="bg-[#28272b] border border-[#3c3a41] rounded-xl">
        <div className="p-4 lg:p-5 border-b border-[#3c3a41] flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-base font-semibold text-white" style={SORA}>
              Investment Performance
            </h2>
            <p className="text-xs text-[#858189] mt-0.5" style={INTER}>
              Wallet balance, per-position value, and trade markers
            </p>
          </div>
          {/* Time Range Selector */}
          <div className="flex bg-[#1e1d21] border border-[#3c3a41] rounded-xl overflow-hidden">
            {TIME_RANGES.map((r) => (
              <button
                key={r.value}
                onClick={() => setRange(r.value)}
                className={`px-4 py-2 text-xs font-semibold transition-all ${
                  range === r.value
                    ? "bg-[#8239ef]/20 text-[#bfa1f5] shadow-inner"
                    : "text-[#858189] hover:text-[#b8b5bb] hover:bg-white/[0.03]"
                }`}
                style={SORA}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
        <div className="p-4 lg:p-5">
          {chartData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={540}>
                <ComposedChart data={chartData} margin={{ top: 10, right: 20, bottom: 0, left: 10 }}>
                  <defs>
                    <linearGradient id="walletGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={COLORS.brand} stopOpacity={0.2} />
                      <stop offset="100%" stopColor={COLORS.brand} stopOpacity={0} />
                    </linearGradient>
                  </defs>

                  <CartesianGrid
                    stroke={COLORS.border}
                    strokeDasharray="3 3"
                    vertical={false}
                    strokeOpacity={0.5}
                  />
                  <XAxis
                    dataKey="time"
                    tick={{ fill: COLORS.muted, fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    interval="preserveStartEnd"
                    minTickGap={60}
                    style={INTER}
                  />
                  <YAxis
                    tick={{ fill: COLORS.muted, fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    domain={["auto", "auto"]}
                    width={55}
                    tickFormatter={(v: number) => `$${v.toFixed(0)}`}
                    style={INTER}
                  />
                  <Tooltip content={<ChartTooltip />} />

                  {/* Starting balance reference */}
                  <ReferenceLine
                    y={STARTING_BALANCE}
                    stroke={COLORS.muted}
                    strokeDasharray="6 4"
                    strokeOpacity={0.4}
                    label={{
                      value: "$100 start",
                      fill: COLORS.muted,
                      fontSize: 10,
                      position: "left",
                    }}
                  />

                  {/* Wallet balance area + line */}
                  <Area
                    type="monotone"
                    dataKey="balance"
                    stroke={COLORS.brand2}
                    strokeWidth={2.5}
                    fill="url(#walletGrad)"
                    dot={false}
                    name="Wallet Balance"
                    connectNulls
                    isAnimationActive={false}
                  />

                  {/* Per-position lines */}
                  {positionIds.map((pid) => {
                    const pos = positionMap.get(pid);
                    if (!pos) return null;
                    const color = getAssetColor(pos.asset);
                    const isClosed = pos.status !== "open";
                    return (
                      <Line
                        key={`pos_${pid}`}
                        type="monotone"
                        dataKey={`pos_${pid}`}
                        stroke={color}
                        strokeWidth={1.5}
                        strokeDasharray={isClosed ? "5 3" : undefined}
                        dot={false}
                        connectNulls
                        name={`${pos.direction.toUpperCase()} ${pos.asset} $${pos.size_usd.toFixed(0)}`}
                        isAnimationActive={false}
                        strokeOpacity={isClosed ? 0.5 : 0.9}
                      />
                    );
                  })}

                  {/* Buy markers */}
                  <Scatter
                    dataKey="buyVal"
                    name="BUY"
                    shape={<BuyMarker />}
                    isAnimationActive={false}
                  />

                  {/* Sell markers */}
                  <Scatter
                    dataKey="sellVal"
                    name="SELL"
                    shape={<SellMarker />}
                    isAnimationActive={false}
                  />

                  <Legend
                    verticalAlign="bottom"
                    iconSize={10}
                    wrapperStyle={{
                      fontSize: 11,
                      color: COLORS.text2,
                      paddingTop: 16,
                      ...INTER,
                    }}
                  />
                </ComposedChart>
              </ResponsiveContainer>

              {/* Position legend with status tags */}
              {positionIds.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {positionIds.map((pid) => {
                    const pos = positionMap.get(pid);
                    if (!pos) return null;
                    const color = getAssetColor(pos.asset);
                    return (
                      <div
                        key={pid}
                        className="flex items-center gap-1.5 px-2.5 py-1 bg-[#1e1d21] border border-[#3c3a41] rounded-lg text-xs"
                        style={INTER}
                      >
                        <span
                          className="w-3 h-0.5 rounded-full inline-block"
                          style={{
                            background: color,
                            borderBottom: pos.status !== "open" ? "1px dashed" : undefined,
                          }}
                        />
                        <span
                          className={`font-semibold ${
                            pos.direction === "long" ? "text-[#84f593]" : "text-[#f2685f]"
                          }`}
                        >
                          {pos.direction.toUpperCase()}
                        </span>
                        <span className="text-[#b8b5bb]" style={{ color }}>
                          {pos.asset}
                        </span>
                        <span className="text-[#858189]">${pos.size_usd.toFixed(0)}</span>
                        <span
                          className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
                            pos.status === "open"
                              ? "bg-[#8239ef]/15 text-[#bfa1f5]"
                              : pos.pnl >= 0
                              ? "bg-[#84f593]/10 text-[#84f593]"
                              : "bg-[#f2685f]/10 text-[#f2685f]"
                          }`}
                        >
                          {pos.status.toUpperCase()}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          ) : (
            <div className="py-20 text-center">
              <div className="text-2xl mb-2">📊</div>
              <p className="text-sm text-[#858189]" style={INTER}>
                No wallet history yet.
              </p>
              <p className="text-xs text-[#656169] mt-1" style={INTER}>
                Data appears once the agent starts trading.
              </p>
            </div>
          )}
        </div>
      </section>

      {/* ────── RISK METRICS ROW ────── */}
      {stats && stats.closed_trades > 0 && (
        <section>
          <h2
            className="text-xs font-semibold uppercase tracking-wider text-[#858189] mb-3"
            style={SORA}
          >
            Risk Metrics
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <RiskCard
              label="Profit Factor"
              value={
                risk.profitFactor === null
                  ? "-"
                  : risk.profitFactor === Infinity
                  ? "∞"
                  : risk.profitFactor.toFixed(2)
              }
              hint="Gross wins / gross losses"
              good={risk.profitFactor !== null && risk.profitFactor > 1}
            />
            <RiskCard
              label="Max Drawdown"
              value={`${risk.maxDrawdownPct.toFixed(1)}%`}
              hint="Peak-to-trough decline"
              good={risk.maxDrawdownPct < 10}
            />
            <RiskCard
              label="Avg Duration"
              value={risk.avgDuration}
              hint="Average trade holding time"
            />
            <RiskCard
              label="Best Trade"
              value={fmtUsd(risk.bestTrade)}
              valueColor={COLORS.up}
              hint="Highest single-trade PnL"
            />
            <RiskCard
              label="Worst Trade"
              value={fmtUsd(risk.worstTrade)}
              valueColor={COLORS.down}
              hint="Lowest single-trade PnL"
            />
            <RiskCard
              label="Sharpe Ratio"
              value={risk.sharpe !== null ? risk.sharpe.toFixed(2) : "-"}
              hint="avg_pnl / std_pnl"
              good={risk.sharpe !== null && risk.sharpe > 0.5}
            />
          </div>
        </section>
      )}

      {/* ────── OPEN POSITIONS ────── */}
      {openPos.length > 0 && (
        <section>
          <h2
            className="text-xs font-semibold uppercase tracking-wider text-[#858189] mb-3"
            style={SORA}
          >
            Open Positions ({openPos.length})
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {openPos.map((p) => {
              const age = Date.now() - new Date(p.opened_at).getTime();
              const snap = latestSnapshotByPos.get(p.id);
              const margin = p.size_usd;
              const unrealizedPnl = snap ? snap.unrealized_pnl : p.pnl;
              const currentValue = margin + unrealizedPnl;
              const color = getAssetColor(p.asset);

              return (
                <div
                  key={p.id}
                  className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-4 transition-colors hover:border-[#656169]"
                  style={{ borderLeftColor: color, borderLeftWidth: 3 }}
                >
                  {/* Top row */}
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded ${
                          p.direction === "long"
                            ? "bg-[#84f593]/10 text-[#84f593]"
                            : "bg-[#f2685f]/10 text-[#f2685f]"
                        }`}
                        style={SORA}
                      >
                        {p.direction.toUpperCase()}
                      </span>
                      <span className="font-semibold text-sm text-white" style={SORA}>
                        {p.asset}
                      </span>
                      <span className="text-xs text-[#858189] font-medium">
                        {p.leverage}x
                      </span>
                    </div>
                    <div className="text-right">
                      <div
                        className={`text-base font-bold tabular-nums ${pnlClass(unrealizedPnl)}`}
                        style={SORA}
                      >
                        {unrealizedPnl >= 0 ? "+" : ""}
                        {fmtUsd(unrealizedPnl)}
                      </div>
                      <div className="text-[10px] text-[#858189]" style={INTER}>
                        {durationStr(age)} open
                      </div>
                    </div>
                  </div>

                  {/* Metrics grid */}
                  <div className="mt-3 grid grid-cols-5 gap-2 text-xs" style={INTER}>
                    <div>
                      <div className="text-[#656169] mb-0.5">Entry</div>
                      <div className="text-[#b8b5bb] tabular-nums">
                        ${p.entry_price.toFixed(2)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[#656169] mb-0.5">Margin</div>
                      <div className="text-[#b8b5bb] tabular-nums">${margin.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-[#656169] mb-0.5">Current Val</div>
                      <div
                        className="tabular-nums font-medium"
                        style={{ color: pnlColor(unrealizedPnl) }}
                      >
                        ${currentValue.toFixed(2)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[#656169] mb-0.5">Stop Loss</div>
                      <div className="text-[#f2685f] tabular-nums">
                        ${p.stop_loss.toFixed(2)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[#656169] mb-0.5">Take Profit</div>
                      <div className="text-[#84f593] tabular-nums">
                        ${p.take_profit.toFixed(2)}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ────── TRADE HISTORY ────── */}
      <section>
        <h2
          className="text-xs font-semibold uppercase tracking-wider text-[#858189] mb-3"
          style={SORA}
        >
          Trade History ({closedPositions.length} closed)
        </h2>
        {closedPositions.length === 0 ? (
          <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-8 text-center">
            <p className="text-sm text-[#858189]" style={INTER}>
              No closed trades yet.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {closedPositions.map((p) => {
              const analysis = analysisById.get(p.analysis_id);
              const isOpen = expandedTrade === p.id;
              const margin = p.size_usd;
              const returnPct = margin > 0 ? (p.pnl / margin) * 100 : 0;
              const dur =
                p.closed_at && p.opened_at
                  ? durationStr(
                      new Date(p.closed_at).getTime() -
                        new Date(p.opened_at).getTime()
                    )
                  : "-";

              return (
                <div
                  key={p.id}
                  className="bg-[#28272b] border border-[#3c3a41] rounded-xl transition-colors hover:border-[#656169] overflow-hidden"
                >
                  {/* Summary row */}
                  <button
                    onClick={() => setExpandedTrade(isOpen ? null : p.id)}
                    className="w-full p-3 lg:p-4 flex items-center justify-between text-left gap-3"
                  >
                    <div className="flex items-center gap-2 flex-wrap min-w-0">
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded shrink-0 ${
                          p.direction === "long"
                            ? "bg-[#84f593]/10 text-[#84f593]"
                            : "bg-[#f2685f]/10 text-[#f2685f]"
                        }`}
                        style={SORA}
                      >
                        {p.direction.toUpperCase()}
                      </span>
                      <span
                        className="font-semibold text-sm"
                        style={{ color: getAssetColor(p.asset), ...SORA }}
                      >
                        {p.asset}
                      </span>
                      <span className="text-xs text-[#858189]" style={INTER}>
                        ${margin.toFixed(0)} @ {p.leverage}x
                      </span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase shrink-0 ${
                          p.status === "stopped"
                            ? "bg-[#f2685f]/10 text-[#f2685f]"
                            : p.pnl >= 0
                            ? "bg-[#84f593]/10 text-[#84f593]"
                            : "bg-[#f2685f]/10 text-[#f2685f]"
                        }`}
                      >
                        {p.status}
                      </span>
                      <span className="text-xs text-[#656169]" style={INTER}>
                        {dur}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 shrink-0">
                      <div className="text-right">
                        <div
                          className={`text-sm font-bold tabular-nums ${pnlClass(p.pnl)}`}
                          style={SORA}
                        >
                          {p.pnl >= 0 ? "+" : ""}
                          {fmtUsd(p.pnl)}
                        </div>
                        <div
                          className={`text-[10px] tabular-nums ${pnlClass(returnPct)}`}
                          style={INTER}
                        >
                          {fmtPct(returnPct)}
                        </div>
                      </div>
                      <span className="text-xs text-[#656169]" style={INTER}>
                        {timeAgo(p.closed_at || p.opened_at)}
                      </span>
                      <svg
                        className={`w-4 h-4 text-[#656169] transition-transform ${
                          isOpen ? "rotate-90" : ""
                        }`}
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="m9 18 6-6-6-6" />
                      </svg>
                    </div>
                  </button>

                  {/* Expanded details */}
                  {isOpen && (
                    <div className="px-4 pb-4 border-t border-[#3c3a41]">
                      <div
                        className="mt-3 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 text-xs"
                        style={INTER}
                      >
                        <div>
                          <div className="text-[#656169] mb-0.5">Entry Price</div>
                          <div className="text-[#b8b5bb] tabular-nums">
                            ${p.entry_price.toFixed(2)}
                          </div>
                        </div>
                        <div>
                          <div className="text-[#656169] mb-0.5">Margin</div>
                          <div className="text-[#b8b5bb] tabular-nums">
                            ${margin.toFixed(2)}
                          </div>
                        </div>
                        <div>
                          <div className="text-[#656169] mb-0.5">Leverage</div>
                          <div className="text-[#b8b5bb] tabular-nums">{p.leverage}x</div>
                        </div>
                        <div>
                          <div className="text-[#656169] mb-0.5">Stop Loss</div>
                          <div className="text-[#f2685f] tabular-nums">
                            ${p.stop_loss.toFixed(2)}
                          </div>
                        </div>
                        <div>
                          <div className="text-[#656169] mb-0.5">Take Profit</div>
                          <div className="text-[#84f593] tabular-nums">
                            ${p.take_profit.toFixed(2)}
                          </div>
                        </div>
                        <div>
                          <div className="text-[#656169] mb-0.5">PnL</div>
                          <div
                            className="tabular-nums font-semibold"
                            style={{ color: pnlColor(p.pnl) }}
                          >
                            {p.pnl >= 0 ? "+" : ""}
                            {fmtUsd(p.pnl)} ({fmtPct(returnPct)})
                          </div>
                        </div>
                      </div>

                      {/* Timestamps */}
                      <div
                        className="mt-2 flex gap-4 text-xs text-[#858189]"
                        style={INTER}
                      >
                        <span>
                          Opened: <span className="text-[#b8b5bb]">{fmtDateTime(p.opened_at)}</span>
                        </span>
                        {p.closed_at && (
                          <span>
                            Closed: <span className="text-[#b8b5bb]">{fmtDateTime(p.closed_at)}</span>
                          </span>
                        )}
                      </div>

                      {/* AI Reasoning */}
                      {analysis && (
                        <div className="mt-3 bg-[#1e1d21] border border-[#3c3a41] rounded-lg p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <svg
                              width="14"
                              height="14"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke={COLORS.brand2}
                              strokeWidth="2"
                            >
                              <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z" />
                              <path d="M12 16v-4M12 8h.01" />
                            </svg>
                            <span
                              className="text-[10px] font-bold uppercase tracking-wider text-[#858189]"
                              style={SORA}
                            >
                              AI Reasoning
                            </span>
                            <span
                              className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${convictionBadge(
                                analysis.conviction_score
                              )}`}
                            >
                              {(analysis.conviction_score * 100).toFixed(0)}% conviction
                            </span>
                          </div>
                          <p
                            className="text-xs text-[#b8b5bb] leading-relaxed"
                            style={INTER}
                          >
                            {analysis.reasoning}
                          </p>
                          {analysis.risk_notes && (
                            <p className="text-xs text-[#F59E0B] mt-2 flex items-center gap-1">
                              <svg
                                width="12"
                                height="12"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                              >
                                <path d="M12 9v4m0 4h.01M10.29 3.86l-8.7 15.04A1 1 0 0 0 2.46 21h19.08a1 1 0 0 0 .87-1.5l-8.7-15.04a1.35 1.35 0 0 0-2.42 0z" />
                              </svg>
                              {analysis.risk_notes}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

/* ─── Risk Metric Card Sub-component ───────────────────────────────────────── */

function RiskCard({
  label,
  value,
  hint,
  valueColor,
  good,
}: {
  label: string;
  value: string;
  hint: string;
  valueColor?: string;
  good?: boolean;
}) {
  return (
    <div
      className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-3 transition-all hover:border-[#656169] group"
      title={hint}
    >
      <div
        className="text-[10px] font-semibold uppercase tracking-wider text-[#858189] mb-1"
        style={SORA}
      >
        {label}
      </div>
      <div
        className="text-lg font-bold tabular-nums"
        style={{
          color: valueColor ?? (good === true ? COLORS.up : good === false ? COLORS.down : COLORS.text),
          ...SORA,
        }}
      >
        {value}
      </div>
      <div className="text-[10px] text-[#656169] mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" style={INTER}>
        {hint}
      </div>
    </div>
  );
}
