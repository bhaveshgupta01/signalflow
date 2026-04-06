"use client";

import { useEffect, useState, useMemo } from "react";
import MetricCard from "@/components/metric-card";
import WalletChart from "@/components/charts/wallet-chart";
import AllocationPie from "@/components/charts/allocation-pie";
import {
  getStats,
  getWalletHistory,
  getAllPositions,
  getOpenPositions,
  getRecentAnalyses,
} from "@/lib/queries";
import { getAssetColor } from "@/lib/colors";
import type { TradingStats, WalletSnapshot, Position, Analysis } from "@/lib/types";

const TIME_RANGES = [
  { value: 60, label: "1H" },
  { value: 360, label: "6H" },
  { value: 1440, label: "1D" },
  { value: 0, label: "ALL" },
];

function convictionBadge(score: number) {
  if (score >= 0.7) return "bg-sf-up/10 text-sf-up";
  if (score >= 0.4) return "bg-sf-warn/10 text-sf-warn";
  return "bg-sf-down/10 text-sf-down";
}

function timeAgo(dateStr: string) {
  const mins = Math.round((Date.now() - new Date(dateStr).getTime()) / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export default function PortfolioPage() {
  const [stats, setStats] = useState<TradingStats | null>(null);
  const [wallet, setWallet] = useState<WalletSnapshot[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [openPos, setOpenPos] = useState<Position[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [range, setRange] = useState(0); // 0 = ALL
  const [expandedTrade, setExpandedTrade] = useState<number | null>(null);

  async function load() {
    const [s, w, p, o, a] = await Promise.all([
      getStats(),
      getWalletHistory(500),
      getAllPositions(200),
      getOpenPositions(),
      getRecentAnalyses(200),
    ]);
    setStats(s);
    setWallet(w);
    setPositions(p);
    setOpenPos(o);
    setAnalyses(a);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);

  const pnl = stats?.total_pnl ?? 0;
  const balance = 100 + pnl;
  const pnlPct = (pnl / 100) * 100;

  // Filter wallet data by time range
  const filteredWallet = range === 0
    ? wallet
    : wallet.filter((s) => Date.now() - new Date(s.timestamp).getTime() < range * 60_000);

  // Build analysis lookup by id
  const analysisById = new Map(analyses.map((a) => [a.id, a]));

  // Portfolio allocation: cash + open positions by asset
  const allocation = useMemo(() => {
    const invested = openPos.reduce((s, p) => s + p.size_usd, 0);
    const cash = Math.max(0, balance - invested);
    const slices: { name: string; value: number }[] = [];

    // Group open positions by asset
    const byAsset: Record<string, number> = {};
    for (const p of openPos) {
      byAsset[p.asset] = (byAsset[p.asset] ?? 0) + p.size_usd;
    }
    for (const [asset, val] of Object.entries(byAsset).sort((a, b) => b[1] - a[1])) {
      slices.push({ name: asset, value: val });
    }
    if (cash > 0) slices.push({ name: "Cash", value: cash });
    return slices;
  }, [openPos, balance]);

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-[1200px]">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-sf-text">Portfolio</h1>
          <p className="text-sm text-sf-muted mt-0.5">
            Wallet balance, PnL growth, and trade history.
          </p>
        </div>
        {/* Time Range Selector */}
        <div className="flex bg-sf-card border border-sf-border rounded-lg overflow-hidden">
          {TIME_RANGES.map((r) => (
            <button
              key={r.value}
              onClick={() => setRange(r.value)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                range === r.value
                  ? "bg-sf-brand/15 text-sf-brand"
                  : "text-sf-muted hover:text-sf-text-2 hover:bg-white/[0.03]"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Top Metrics */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <MetricCard
            label="Balance"
            value={`$${balance.toFixed(2)}`}
            delta={`${pnl >= 0 ? "+" : ""}$${pnl.toFixed(2)} (${pnl >= 0 ? "+" : ""}${pnlPct.toFixed(1)}%)`}
            deltaColor={pnl >= 0 ? "text-sf-up" : "text-sf-down"}
          />
          <MetricCard
            label="Win Rate"
            value={`${stats.win_rate.toFixed(1)}%`}
            delta={`${stats.wins}W / ${stats.closed_trades - stats.wins}L`}
            deltaColor={stats.win_rate >= 50 ? "text-sf-up" : "text-sf-down"}
          />
          <MetricCard
            label="Total Trades"
            value={String(stats.total_trades)}
            delta={`${stats.closed_trades} closed`}
          />
          <MetricCard
            label="Open"
            value={String(openPos.length)}
            delta={`$${stats.open_exposure.toFixed(0)} exposure`}
          />
          <MetricCard
            label="Starting"
            value="$100.00"
            delta="paper wallet"
          />
        </div>
      )}

      {/* Wallet Chart */}
      <section className="bg-sf-card border border-sf-border rounded-lg">
        <div className="p-4 border-b border-sf-border flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-sf-text">Investment Performance</h2>
            <p className="text-xs text-sf-muted mt-0.5">Balance + PnL over time</p>
          </div>
        </div>
        <div className="p-4">
          {filteredWallet.length > 0 ? (
            <WalletChart data={filteredWallet} />
          ) : (
            <div className="py-12 text-center">
              <p className="text-sm text-sf-muted">No wallet history yet.</p>
              <p className="text-xs text-sf-subtle mt-1">Data appears once the agent starts trading.</p>
            </div>
          )}
        </div>
      </section>

      {/* Portfolio Allocation Pie */}
      {allocation.length > 0 && (
        <section className="bg-sf-card border border-sf-border rounded-lg">
          <div className="p-4 border-b border-sf-border">
            <h2 className="text-sm font-semibold text-sf-text">Current Allocation</h2>
            <p className="text-xs text-sf-muted mt-0.5">Cash vs open positions by asset</p>
          </div>
          <div className="p-4">
            <AllocationPie data={allocation} />
          </div>
        </section>
      )}

      {/* Open Positions */}
      {openPos.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">
            Open Positions ({openPos.length})
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {openPos.map((p) => {
              const age = Math.round((Date.now() - new Date(p.opened_at).getTime()) / 3600_000);
              return (
                <div
                  key={p.id}
                  className="bg-sf-card border border-sf-border rounded-lg p-4 transition-colors hover:border-sf-border-bold"
                  style={{ borderLeftColor: getAssetColor(p.asset), borderLeftWidth: 3 }}
                >
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                        p.direction === "long" ? "bg-sf-up/10 text-sf-up" : "bg-sf-down/10 text-sf-down"
                      }`}>
                        {p.direction.toUpperCase()}
                      </span>
                      <span className="font-semibold text-sm">{p.asset}</span>
                      <span className="text-xs text-sf-subtle">{p.leverage}x</span>
                      <span className="text-xs text-sf-subtle">{age}h</span>
                    </div>
                    <span className={`text-sm font-semibold tabular-nums ${p.pnl >= 0 ? "text-sf-up" : "text-sf-down"}`}>
                      {p.pnl >= 0 ? "+" : ""}${p.pnl.toFixed(2)}
                    </span>
                  </div>
                  <div className="mt-3 grid grid-cols-4 gap-2 text-xs">
                    <div>
                      <div className="text-sf-subtle mb-0.5">Entry</div>
                      <div className="text-sf-text-2 tabular-nums">${p.entry_price.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-sf-subtle mb-0.5">Stop Loss</div>
                      <div className="text-sf-down tabular-nums">${p.stop_loss.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-sf-subtle mb-0.5">Take Profit</div>
                      <div className="text-sf-up tabular-nums">${p.take_profit.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-sf-subtle mb-0.5">Size</div>
                      <div className="text-sf-text-2 tabular-nums">${p.size_usd.toFixed(0)}</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Trade History with expandable details */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">
          Trade History ({positions.length})
        </h2>
        {positions.length === 0 ? (
          <div className="bg-sf-card border border-sf-border rounded-lg p-8 text-center">
            <p className="text-sm text-sf-muted">No trades yet.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {positions.slice(0, 30).map((p) => {
              const analysis = analysisById.get(p.analysis_id);
              const isOpen = expandedTrade === p.id;
              return (
                <div key={p.id} className="bg-sf-card border border-sf-border rounded-lg transition-colors hover:border-sf-border-bold overflow-hidden">
                  {/* Summary row */}
                  <button
                    onClick={() => setExpandedTrade(isOpen ? null : p.id)}
                    className="w-full p-3 flex items-center justify-between text-left"
                  >
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                        p.direction === "long" ? "bg-sf-up/10 text-sf-up" : "bg-sf-down/10 text-sf-down"
                      }`}>
                        {p.direction.toUpperCase()}
                      </span>
                      <span className="font-medium text-sm" style={{ color: getAssetColor(p.asset) }}>{p.asset}</span>
                      <span className="text-xs text-sf-muted">${p.size_usd.toFixed(0)} @ {p.leverage}x</span>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        p.status === "open"
                          ? "bg-sf-brand/10 text-sf-brand"
                          : p.pnl >= 0
                          ? "bg-sf-up/10 text-sf-up"
                          : "bg-sf-down/10 text-sf-down"
                      }`}>
                        {p.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-sm font-semibold tabular-nums ${p.pnl >= 0 ? "text-sf-up" : "text-sf-down"}`}>
                        {p.pnl >= 0 ? "+" : ""}${p.pnl.toFixed(2)}
                      </span>
                      <span className="text-xs text-sf-subtle">{timeAgo(p.opened_at)}</span>
                      <svg className={`w-4 h-4 text-sf-subtle transition-transform ${isOpen ? "rotate-90" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="m9 18 6-6-6-6" />
                      </svg>
                    </div>
                  </button>

                  {/* Expanded details */}
                  {isOpen && (
                    <div className="px-3 pb-3 border-t border-sf-border">
                      <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                        <div>
                          <div className="text-sf-subtle mb-0.5">Entry Price</div>
                          <div className="text-sf-text-2 tabular-nums">${p.entry_price.toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-sf-subtle mb-0.5">Stop Loss</div>
                          <div className="text-sf-down tabular-nums">${p.stop_loss.toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-sf-subtle mb-0.5">Take Profit</div>
                          <div className="text-sf-up tabular-nums">${p.take_profit.toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-sf-subtle mb-0.5">Opened</div>
                          <div className="text-sf-text-2">{new Date(p.opened_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</div>
                        </div>
                      </div>
                      {p.closed_at && (
                        <div className="mt-2 text-xs">
                          <span className="text-sf-subtle">Closed: </span>
                          <span className="text-sf-text-2">{new Date(p.closed_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                        </div>
                      )}

                      {/* AI Reasoning from analysis */}
                      {analysis && (
                        <div className="mt-3 bg-sf-surface border border-sf-border rounded-md p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-sf-subtle">AI Reasoning</span>
                            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${convictionBadge(analysis.conviction_score)}`}>
                              {(analysis.conviction_score * 100).toFixed(0)}% conviction
                            </span>
                          </div>
                          <p className="text-xs text-sf-text-2 leading-relaxed">
                            {analysis.reasoning}
                          </p>
                          {analysis.risk_notes && (
                            <p className="text-xs text-sf-warn mt-2 flex items-center gap-1">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v4m0 4h.01M10.29 3.86l-8.7 15.04A1 1 0 0 0 2.46 21h19.08a1 1 0 0 0 .87-1.5l-8.7-15.04a1.35 1.35 0 0 0-2.42 0z" /></svg>
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
