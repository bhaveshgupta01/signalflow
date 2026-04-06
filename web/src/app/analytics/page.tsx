"use client";

import { useEffect, useState, useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import MetricCard from "@/components/metric-card";
import PnlScatter from "@/components/charts/pnl-scatter";
import {
  getStats,
  getAllPositions,
  getRecentAnalyses,
  getRecentDecisions,
} from "@/lib/queries";
import { COLORS, getAssetColor } from "@/lib/colors";
import type { TradingStats, Position, Analysis, AgentDecision } from "@/lib/types";

function convictionColor(score: number) {
  if (score >= 0.7) return "bg-sf-up/10 text-sf-up";
  if (score >= 0.4) return "bg-sf-warn/10 text-sf-warn";
  return "bg-sf-down/10 text-sf-down";
}

export default function AnalyticsPage() {
  const [stats, setStats] = useState<TradingStats | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);

  async function load() {
    const [s, p, a, d] = await Promise.all([
      getStats(),
      getAllPositions(200),
      getRecentAnalyses(200),
      getRecentDecisions(100),
    ]);
    setStats(s);
    setPositions(p);
    setAnalyses(a);
    setDecisions(d);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);

  const closed = positions.filter((p) => p.status !== "open");
  const wins = closed.filter((p) => p.pnl > 0);
  const losses = closed.filter((p) => p.pnl < 0);
  const avgWin = wins.reduce((s, p) => s + p.pnl, 0) / (wins.length || 1);
  const avgLoss = losses.reduce((s, p) => s + p.pnl, 0) / (losses.length || 1);
  const avgConviction = analyses.length > 0
    ? analyses.reduce((s, a) => s + a.conviction_score, 0) / analyses.length
    : 0;

  // Asset allocation breakdown (from all positions, not just open)
  const assetAlloc = useMemo(() => {
    const map: Record<string, { open: number; closed: number }> = {};
    for (const p of positions) {
      if (!map[p.asset]) map[p.asset] = { open: 0, closed: 0 };
      if (p.status === "open") map[p.asset].open += p.size_usd;
      else map[p.asset].closed += p.size_usd;
    }
    return Object.entries(map).sort((a, b) => (b[1].open + b[1].closed) - (a[1].open + a[1].closed));
  }, [positions]);

  // Agent Activity data (last 20 cycles)
  const activityData = useMemo(() => {
    return decisions.slice(0, 20).reverse().map((d) => ({
      cycle: d.cycle_id.slice(0, 8),
      signals: d.signals_detected,
      trades: d.trades_executed,
    }));
  }, [decisions]);

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-[1200px]">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-sf-text">Agent Performance</h1>
        <p className="text-sm text-sf-muted mt-0.5">
          Conviction vs returns, decision quality, and asset allocation.
        </p>
      </div>

      {/* Summary */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <MetricCard
            label="Win Rate"
            value={`${stats.win_rate.toFixed(1)}%`}
            delta={`${stats.wins}W / ${stats.closed_trades - stats.wins}L`}
            deltaColor={stats.win_rate >= 50 ? "text-sf-up" : "text-sf-down"}
          />
          <MetricCard
            label="Total PnL"
            value={`$${stats.total_pnl.toFixed(2)}`}
            delta={`${stats.total_pnl >= 0 ? "+" : ""}${((stats.total_pnl / 100) * 100).toFixed(1)}%`}
            deltaColor={stats.total_pnl >= 0 ? "text-sf-up" : "text-sf-down"}
          />
          <MetricCard
            label="Avg Win"
            value={`+$${avgWin.toFixed(2)}`}
            delta={`${wins.length} trades`}
            deltaColor="text-sf-up"
          />
          <MetricCard
            label="Avg Loss"
            value={`$${avgLoss.toFixed(2)}`}
            delta={`${losses.length} trades`}
            deltaColor="text-sf-down"
          />
          <MetricCard
            label="Analyses"
            value={String(analyses.length)}
            delta="total produced"
          />
          <MetricCard
            label="Avg Conviction"
            value={`${(avgConviction * 100).toFixed(0)}%`}
            delta="across all analyses"
          />
        </div>
      )}

      {/* Charts row - Conviction vs PnL + Asset Allocation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* PnL Scatter - 2/3 */}
        <section className="bg-sf-card border border-sf-border rounded-lg lg:col-span-2">
          <div className="p-4 border-b border-sf-border">
            <h2 className="text-sm font-semibold text-sf-text">Conviction vs PnL</h2>
            <p className="text-xs text-sf-muted mt-0.5">Higher conviction should correlate with better returns</p>
          </div>
          <div className="p-4">
            {closed.length > 0 ? (
              <PnlScatter positions={positions} analyses={analyses} />
            ) : (
              <div className="py-12 text-center">
                <p className="text-sm text-sf-muted">No closed trades yet.</p>
              </div>
            )}
          </div>
        </section>

        {/* Asset Allocation - 1/3 */}
        <section className="bg-sf-card border border-sf-border rounded-lg">
          <div className="p-4 border-b border-sf-border">
            <h2 className="text-sm font-semibold text-sf-text">Asset Allocation</h2>
            <p className="text-xs text-sf-muted mt-0.5">By traded volume</p>
          </div>
          <div className="p-4">
            {assetAlloc.length > 0 ? (
              <div className="space-y-3">
                {assetAlloc.map(([asset, vol]) => {
                  const total = vol.open + vol.closed;
                  const maxTotal = assetAlloc[0][1].open + assetAlloc[0][1].closed;
                  const pct = maxTotal > 0 ? (total / maxTotal) * 100 : 0;
                  return (
                    <div key={asset}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-medium" style={{ color: getAssetColor(asset) }}>{asset}</span>
                        <span className="text-sf-muted tabular-nums">${total.toFixed(0)}</span>
                      </div>
                      <div className="w-full bg-sf-bg rounded-full h-1.5 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${Math.max(pct, 3)}%`, background: getAssetColor(asset), opacity: 0.7 }}
                        />
                      </div>
                      {vol.open > 0 && (
                        <div className="text-[10px] text-sf-brand mt-0.5">${vol.open.toFixed(0)} open</div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="py-8 text-center">
                <p className="text-xs text-sf-muted">No positions yet.</p>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Agent Activity Chart */}
      {activityData.length > 0 && (
        <section className="bg-sf-card border border-sf-border rounded-lg">
          <div className="p-4 border-b border-sf-border">
            <h2 className="text-sm font-semibold text-sf-text">Agent Activity</h2>
            <p className="text-xs text-sf-muted mt-0.5">Signals detected vs trades executed per cycle</p>
          </div>
          <div className="p-4">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={activityData}>
                <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="cycle" tick={{ fill: COLORS.muted, fontSize: 10 }} axisLine={false} tickLine={false} angle={-45} textAnchor="end" height={50} />
                <YAxis tick={{ fill: COLORS.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: COLORS.card, border: `1px solid ${COLORS.borderBold}`, borderRadius: 8, color: COLORS.text, fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11, color: COLORS.muted }} />
                <Bar dataKey="signals" name="Signals" fill={COLORS.brand} opacity={0.7} radius={[4, 4, 0, 0]} />
                <Bar dataKey="trades" name="Trades" fill={COLORS.up} opacity={0.7} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Decision Log Table */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">Decision Log</h2>
        {decisions.length === 0 ? (
          <div className="bg-sf-card border border-sf-border rounded-lg p-8 text-center">
            <p className="text-sm text-sf-muted">No decisions logged yet.</p>
          </div>
        ) : (
          <div className="bg-sf-card border border-sf-border rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-sf-border bg-sf-surface/50">
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Cycle</th>
                    <th className="text-center px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Signals</th>
                    <th className="text-center px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Analyses</th>
                    <th className="text-center px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Trades</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {decisions.slice(0, 20).map((d) => (
                    <tr key={d.id} className="border-b border-sf-border/50 hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-2.5 font-mono text-xs text-sf-brand">{d.cycle_id.slice(0, 12)}</td>
                      <td className="px-4 py-2.5 text-center tabular-nums text-sf-text-2">{d.signals_detected}</td>
                      <td className="px-4 py-2.5 text-center tabular-nums text-sf-text-2">{d.analyses_produced}</td>
                      <td className="px-4 py-2.5 text-center tabular-nums text-sf-text-2">{d.trades_executed}</td>
                      <td className="px-4 py-2.5 text-xs text-sf-muted tabular-nums">
                        {new Date(d.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* Recent AI Analyses */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">Recent AI Analyses</h2>
        <div className="space-y-2">
          {analyses.slice(0, 10).map((a) => (
            <details
              key={a.id}
              className="bg-sf-card border border-sf-border rounded-lg transition-colors hover:border-sf-border-bold"
            >
              <summary className="cursor-pointer p-3 flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                    a.suggested_direction === "long" ? "bg-sf-up/10 text-sf-up" : "bg-sf-down/10 text-sf-down"
                  }`}>
                    {a.suggested_direction.toUpperCase()}
                  </span>
                  <span className="font-medium text-sf-text">{a.suggested_asset}</span>
                  <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${convictionColor(a.conviction_score)}`}>
                    {(a.conviction_score * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-sf-muted tabular-nums">${a.suggested_size_usd.toFixed(0)}</span>
                  <svg className="w-4 h-4 text-sf-subtle chevron transition-transform" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m9 18 6-6-6-6" />
                  </svg>
                </div>
              </summary>
              <div className="px-3 pb-3 border-t border-sf-border">
                <p className="text-sm text-sf-text-2 mt-3 leading-relaxed">{a.reasoning}</p>
                {a.risk_notes && (
                  <p className="text-xs text-sf-warn mt-2 flex items-center gap-1">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v4m0 4h.01M10.29 3.86l-8.7 15.04A1 1 0 0 0 2.46 21h19.08a1 1 0 0 0 .87-1.5l-8.7-15.04a1.35 1.35 0 0 0-2.42 0z" /></svg>
                    {a.risk_notes}
                  </p>
                )}
              </div>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
