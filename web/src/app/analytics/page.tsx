"use client";

import { useEffect, useState, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import MetricCard from "@/components/metric-card";
import PnlScatter from "@/components/charts/pnl-scatter";
import {
  getStats,
  getAllPositions,
  getRecentAnalyses,
  getRecentDecisions,
} from "@/lib/queries";
import { COLORS, CHART_COLORS, getAssetColor } from "@/lib/colors";
import type {
  TradingStats,
  Position,
  Analysis,
  AgentDecision,
} from "@/lib/types";

function convictionColor(score: number) {
  if (score >= 0.7) return "bg-[#bfa1f5]/10 text-[#bfa1f5] border border-[#bfa1f5]/20";
  if (score >= 0.4) return "bg-[#F59E0B]/10 text-[#F59E0B] border border-[#F59E0B]/20";
  return "bg-[#858189]/10 text-[#858189] border border-[#858189]/20";
}

function directionBadge(dir: "long" | "short") {
  return dir === "long"
    ? "bg-[#84f593]/10 text-[#84f593] border border-[#84f593]/20"
    : "bg-[#f2685f]/10 text-[#f2685f] border border-[#f2685f]/20";
}

/* Custom tooltip for pie chart */
function PieTooltip({ active, payload }: { active?: boolean; payload?: Array<{ name: string; value: number; payload: { name: string; value: number; fill: string } }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  return (
    <div
      className="rounded-lg border px-3 py-2"
      style={{
        background: COLORS.card,
        border: `1px solid ${COLORS.borderBold}`,
        fontSize: 12,
        color: COLORS.text,
      }}
    >
      <div className="flex items-center gap-2">
        <div
          className="w-2.5 h-2.5 rounded-full"
          style={{ background: d.payload.fill }}
        />
        <span className="font-medium">{d.name}</span>
      </div>
      <div className="text-[#858189] mt-0.5">${d.value.toFixed(0)} volume</div>
    </div>
  );
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
  const grossWins = wins.reduce((s, p) => s + p.pnl, 0);
  const grossLosses = Math.abs(losses.reduce((s, p) => s + p.pnl, 0));
  const profitFactor = grossLosses > 0 ? grossWins / grossLosses : grossWins > 0 ? Infinity : 0;
  const avgConviction =
    analyses.length > 0
      ? analyses.reduce((s, a) => s + a.conviction_score, 0) / analyses.length
      : 0;

  // Asset allocation for donut chart
  const donutData = useMemo(() => {
    const map: Record<string, number> = {};
    for (const p of positions) {
      map[p.asset] = (map[p.asset] || 0) + p.size_usd;
    }
    return Object.entries(map)
      .sort((a, b) => b[1] - a[1])
      .map(([name, value]) => ({
        name,
        value,
        fill: getAssetColor(name),
      }));
  }, [positions]);

  // Agent Activity data (last 20 cycles)
  const activityData = useMemo(() => {
    return decisions
      .slice(0, 20)
      .reverse()
      .map((d) => ({
        cycle: d.cycle_id.slice(0, 6),
        signals: d.signals_detected,
        trades: d.trades_executed,
      }));
  }, [decisions]);

  // Win rate by asset
  const winRateByAsset = useMemo(() => {
    const map: Record<string, { wins: number; total: number }> = {};
    for (const p of closed) {
      if (!map[p.asset]) map[p.asset] = { wins: 0, total: 0 };
      map[p.asset].total++;
      if (p.pnl > 0) map[p.asset].wins++;
    }
    return Object.entries(map)
      .map(([asset, { wins, total }]) => ({
        asset,
        winRate: total > 0 ? (wins / total) * 100 : 0,
        trades: total,
        fill: getAssetColor(asset),
      }))
      .sort((a, b) => b.winRate - a.winRate);
  }, [closed]);

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1
            className="text-2xl font-bold text-white tracking-tight"
            style={{ fontFamily: "'Sora', sans-serif" }}
          >
            Agent Performance
          </h1>
          <p
            className="text-sm text-[#858189] mt-1"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            Conviction analysis, decision quality, and portfolio attribution
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-[#858189]">
          <span className="tabular-nums">{closed.length} closed trades</span>
          <span className="text-[#3c3a41]">|</span>
          <span className="tabular-nums">{analyses.length} analyses</span>
        </div>
      </div>

      {/* Summary Metrics - 6 cards */}
      {stats && (
        <section>
          <h2
            className="text-[11px] font-semibold uppercase tracking-widest text-[#858189] mb-3"
            style={{ fontFamily: "'Sora', sans-serif" }}
          >
            Performance Summary
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <MetricCard
              label="Win Rate"
              value={`${stats.win_rate.toFixed(1)}%`}
              delta={`${stats.wins}W / ${stats.closed_trades - stats.wins}L`}
              deltaColor={
                stats.win_rate >= 50 ? "text-[#84f593]" : "text-[#f2685f]"
              }
            />
            <MetricCard
              label="Total PnL"
              value={`${stats.total_pnl >= 0 ? "+" : ""}$${stats.total_pnl.toFixed(2)}`}
              delta={`${stats.total_pnl >= 0 ? "+" : ""}${((stats.total_pnl / 100) * 100).toFixed(1)}% return`}
              deltaColor={
                stats.total_pnl >= 0 ? "text-[#84f593]" : "text-[#f2685f]"
              }
            />
            <MetricCard
              label="Avg Win"
              value={`+$${avgWin.toFixed(2)}`}
              delta={`${wins.length} winning trades`}
              deltaColor="text-[#84f593]"
            />
            <MetricCard
              label="Avg Loss"
              value={`-$${Math.abs(avgLoss).toFixed(2)}`}
              delta={`${losses.length} losing trades`}
              deltaColor="text-[#f2685f]"
            />
            <MetricCard
              label="Profit Factor"
              value={
                profitFactor === Infinity
                  ? "INF"
                  : profitFactor.toFixed(2)
              }
              delta={`$${grossWins.toFixed(0)} / $${grossLosses.toFixed(0)}`}
              deltaColor={
                profitFactor >= 1.5
                  ? "text-[#84f593]"
                  : profitFactor >= 1
                    ? "text-[#F59E0B]"
                    : "text-[#f2685f]"
              }
            />
            <MetricCard
              label="Avg Conviction"
              value={`${(avgConviction * 100).toFixed(0)}%`}
              delta={`across ${analyses.length} analyses`}
              deltaColor="text-[#bfa1f5]"
            />
          </div>
        </section>
      )}

      {/* Conviction vs PnL Scatter */}
      <section className="bg-[#28272b] border border-[#3c3a41] rounded-xl hover:border-[#656169] transition-colors">
        <div className="p-5 border-b border-[#3c3a41]">
          <h2
            className="text-sm font-semibold text-white"
            style={{ fontFamily: "'Sora', sans-serif" }}
          >
            Conviction vs PnL
          </h2>
          <p
            className="text-xs text-[#858189] mt-0.5"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            Each dot is a closed trade. Higher conviction should correlate with
            better returns.
          </p>
        </div>
        <div className="p-5">
          {closed.length > 0 ? (
            <PnlScatter positions={positions} analyses={analyses} />
          ) : (
            <div className="py-16 text-center">
              <svg
                width="32"
                height="32"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#656169"
                strokeWidth="1.5"
                className="mx-auto mb-2"
              >
                <circle cx="12" cy="12" r="10" />
                <path d="M8 12h8M12 8v8" strokeLinecap="round" />
              </svg>
              <p
                className="text-sm text-[#858189]"
                style={{ fontFamily: "'Inter', sans-serif" }}
              >
                No closed trades yet
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Two-column: Asset Allocation Donut + Agent Activity Bar */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Asset Allocation Donut */}
        <section className="bg-[#28272b] border border-[#3c3a41] rounded-xl hover:border-[#656169] transition-colors">
          <div className="p-5 border-b border-[#3c3a41]">
            <h2
              className="text-sm font-semibold text-white"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              Asset Allocation
            </h2>
            <p
              className="text-xs text-[#858189] mt-0.5"
              style={{ fontFamily: "'Inter', sans-serif" }}
            >
              Volume distribution by asset
            </p>
          </div>
          <div className="p-5">
            {donutData.length > 0 ? (
              <div className="flex items-center gap-4">
                <ResponsiveContainer width="60%" height={220}>
                  <PieChart>
                    <Pie
                      data={donutData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={90}
                      paddingAngle={2}
                      strokeWidth={0}
                    >
                      {donutData.map((entry, i) => (
                        <Cell
                          key={entry.name}
                          fill={entry.fill}
                          opacity={0.85}
                        />
                      ))}
                    </Pie>
                    <Tooltip content={<PieTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex-1 space-y-2">
                  {donutData.map((d) => {
                    const totalVol = donutData.reduce(
                      (s, x) => s + x.value,
                      0
                    );
                    const pct =
                      totalVol > 0 ? ((d.value / totalVol) * 100).toFixed(1) : "0";
                    return (
                      <div
                        key={d.name}
                        className="flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <div
                            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                            style={{ background: d.fill }}
                          />
                          <span
                            className="text-xs font-medium text-white"
                            style={{ fontFamily: "'Inter', sans-serif" }}
                          >
                            {d.name}
                          </span>
                        </div>
                        <span className="text-xs tabular-nums text-[#858189]">
                          {pct}%
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="py-12 text-center">
                <p
                  className="text-sm text-[#858189]"
                  style={{ fontFamily: "'Inter', sans-serif" }}
                >
                  No positions yet
                </p>
              </div>
            )}
          </div>
        </section>

        {/* Agent Activity */}
        <section className="bg-[#28272b] border border-[#3c3a41] rounded-xl hover:border-[#656169] transition-colors">
          <div className="p-5 border-b border-[#3c3a41]">
            <h2
              className="text-sm font-semibold text-white"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              Agent Activity
            </h2>
            <p
              className="text-xs text-[#858189] mt-0.5"
              style={{ fontFamily: "'Inter', sans-serif" }}
            >
              Signals detected vs trades executed per cycle (last 20)
            </p>
          </div>
          <div className="p-5">
            {activityData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={activityData} barGap={2}>
                  <CartesianGrid
                    stroke={COLORS.border}
                    strokeDasharray="3 3"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="cycle"
                    tick={{ fill: COLORS.muted, fontSize: 9 }}
                    axisLine={false}
                    tickLine={false}
                    angle={-45}
                    textAnchor="end"
                    height={40}
                  />
                  <YAxis
                    tick={{ fill: COLORS.muted, fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={30}
                  />
                  <Tooltip
                    contentStyle={{
                      background: COLORS.card,
                      border: `1px solid ${COLORS.borderBold}`,
                      borderRadius: 8,
                      color: COLORS.text,
                      fontSize: 12,
                    }}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 11, color: COLORS.muted }}
                  />
                  <Bar
                    dataKey="signals"
                    name="Signals"
                    fill={COLORS.brand}
                    opacity={0.8}
                    radius={[3, 3, 0, 0]}
                  />
                  <Bar
                    dataKey="trades"
                    name="Trades"
                    fill={COLORS.up}
                    opacity={0.8}
                    radius={[3, 3, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="py-12 text-center">
                <p
                  className="text-sm text-[#858189]"
                  style={{ fontFamily: "'Inter', sans-serif" }}
                >
                  No decision cycles yet
                </p>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Win Rate by Asset */}
      {winRateByAsset.length > 0 && (
        <section className="bg-[#28272b] border border-[#3c3a41] rounded-xl hover:border-[#656169] transition-colors">
          <div className="p-5 border-b border-[#3c3a41]">
            <h2
              className="text-sm font-semibold text-white"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              Win Rate by Asset
            </h2>
            <p
              className="text-xs text-[#858189] mt-0.5"
              style={{ fontFamily: "'Inter', sans-serif" }}
            >
              Performance breakdown across traded instruments
            </p>
          </div>
          <div className="p-5">
            <div className="space-y-3">
              {winRateByAsset.map((d) => (
                <div key={d.asset}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ background: d.fill }}
                      />
                      <span
                        className="text-sm font-medium text-white"
                        style={{ fontFamily: "'Inter', sans-serif" }}
                      >
                        {d.asset}
                      </span>
                      <span className="text-[10px] text-[#858189] tabular-nums">
                        ({d.trades} trade{d.trades !== 1 ? "s" : ""})
                      </span>
                    </div>
                    <span
                      className={`text-sm font-semibold tabular-nums ${
                        d.winRate >= 50 ? "text-[#84f593]" : "text-[#f2685f]"
                      }`}
                    >
                      {d.winRate.toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-full bg-[#1e1d21] rounded-full h-2 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${Math.max(d.winRate, 2)}%`,
                        background:
                          d.winRate >= 50
                            ? `linear-gradient(90deg, ${d.fill}, ${d.fill}cc)`
                            : `linear-gradient(90deg, #f2685f, #f2685fcc)`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Decision Log */}
      <section>
        <h2
          className="text-[11px] font-semibold uppercase tracking-widest text-[#858189] mb-3"
          style={{ fontFamily: "'Sora', sans-serif" }}
        >
          Decision Log
        </h2>
        {analyses.length === 0 ? (
          <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-10 text-center">
            <p
              className="text-sm text-[#858189]"
              style={{ fontFamily: "'Inter', sans-serif" }}
            >
              No analyses logged yet
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {analyses.slice(0, 20).map((a) => (
              <details
                key={a.id}
                className="bg-[#28272b] border border-[#3c3a41] rounded-xl transition-all hover:border-[#656169] group"
              >
                <summary className="cursor-pointer p-4 flex items-center justify-between text-sm list-none [&::-webkit-details-marker]:hidden">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span
                      className={`text-[11px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-md ${directionBadge(a.suggested_direction)}`}
                    >
                      {a.suggested_direction.toUpperCase()}
                    </span>
                    <span
                      className="font-semibold text-white"
                      style={{ fontFamily: "'Sora', sans-serif" }}
                    >
                      {a.suggested_asset}
                    </span>
                    <span
                      className={`text-[11px] font-semibold px-2 py-0.5 rounded-md ${convictionColor(a.conviction_score)}`}
                    >
                      {(a.conviction_score * 100).toFixed(0)}% conviction
                    </span>
                    <span className="text-xs text-[#b8b5bb] tabular-nums">
                      ${a.suggested_size_usd.toFixed(0)} size
                    </span>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="text-[11px] text-[#858189] tabular-nums hidden sm:inline">
                      {new Date(a.created_at).toLocaleString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                    <svg
                      className="w-4 h-4 text-[#656169] transition-transform group-open:rotate-90"
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
                </summary>
                <div className="px-4 pb-4 border-t border-[#3c3a41]">
                  <div className="mt-3">
                    <div
                      className="text-[10px] font-semibold uppercase tracking-widest text-[#858189] mb-1"
                      style={{ fontFamily: "'Sora', sans-serif" }}
                    >
                      Reasoning
                    </div>
                    <p
                      className="text-sm text-[#b8b5bb] leading-relaxed"
                      style={{ fontFamily: "'Inter', sans-serif" }}
                    >
                      {a.reasoning}
                    </p>
                  </div>
                  {a.risk_notes && (
                    <div className="mt-3">
                      <div
                        className="text-[10px] font-semibold uppercase tracking-widest text-[#858189] mb-1"
                        style={{ fontFamily: "'Sora', sans-serif" }}
                      >
                        Risk Notes
                      </div>
                      <div className="flex items-start gap-2 bg-[#F59E0B]/5 border border-[#F59E0B]/15 rounded-lg px-3 py-2">
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="#F59E0B"
                          strokeWidth="2"
                          className="flex-shrink-0 mt-0.5"
                        >
                          <path d="M12 9v4m0 4h.01M10.29 3.86l-8.7 15.04A1 1 0 0 0 2.46 21h19.08a1 1 0 0 0 .87-1.5l-8.7-15.04a1.35 1.35 0 0 0-2.42 0z" />
                        </svg>
                        <p
                          className="text-xs text-[#F59E0B] leading-relaxed"
                          style={{ fontFamily: "'Inter', sans-serif" }}
                        >
                          {a.risk_notes}
                        </p>
                      </div>
                    </div>
                  )}
                  <div className="mt-3 pt-2 border-t border-[#3c3a41]/50 flex items-center gap-4 text-[10px] text-[#858189] tabular-nums">
                    <span>
                      ID: {a.id}
                    </span>
                    <span>
                      Signal: #{a.signal_id}
                    </span>
                    <span>
                      {new Date(a.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
              </details>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
