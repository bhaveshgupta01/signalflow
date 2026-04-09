"use client";

import { useEffect, useState } from "react";
import MetricCard from "@/components/metric-card";
import SignalCard from "@/components/signal-card";
import {
  getStats,
  getRecentDecisions,
  getRecentSignals,
  getRecentAnalyses,
  getOpenPositions,
} from "@/lib/queries";
import type {
  TradingStats,
  AgentDecision,
  Signal,
  Analysis,
  Position,
} from "@/lib/types";

const BOBA_TOOLS = [
  {
    name: "Polymarket Scanner",
    prefix: "pm_*",
    desc: "Prediction market price moves that may signal real-world events.",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
  },
  {
    name: "KOL Wallet Tracker",
    prefix: "get_kol*",
    desc: "Whale and influencer wallets for smart-money positioning.",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
  {
    name: "Funding Rate Monitor",
    prefix: "hl_funding*",
    desc: "Perpetual swap funding rates to detect crowded positions.",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </svg>
    ),
  },
  {
    name: "Cross-Chain Arb",
    prefix: "crosschain_*",
    desc: "Token price comparison across chains for mispricing.",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5" />
      </svg>
    ),
  },
];

const PIPELINE_STEPS = [
  { label: "Triggers", sublabel: "Signals Detected" },
  { label: "Analyzer", sublabel: "Analyses Run" },
  { label: "Risk Gate", sublabel: "Risk Checked" },
  { label: "Executor", sublabel: "Trades Placed" },
  { label: "Manager", sublabel: "Open Positions" },
];

function ProgressBar({
  label,
  value,
  max,
  color,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
}) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const isHigh = pct >= 80;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span
          className="text-xs font-medium text-[#b8b5bb]"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          {label}
        </span>
        <span
          className="text-xs tabular-nums font-semibold"
          style={{ color: isHigh ? "#f2685f" : "#b8b5bb" }}
        >
          {typeof value === "number" && value % 1 !== 0
            ? `$${value.toFixed(0)}`
            : value}{" "}
          <span className="text-[#858189] font-normal">
            / {typeof max === "number" && max >= 100 ? `$${max.toLocaleString()}` : max}
          </span>
        </span>
      </div>
      <div className="w-full bg-[#1e1d21] rounded-full h-2 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${Math.max(pct, 1)}%`,
            background: isHigh
              ? "linear-gradient(90deg, #f2685f, #eb2314)"
              : `linear-gradient(90deg, ${color}, ${color}dd)`,
          }}
        />
      </div>
      <div className="text-right mt-1">
        <span className="text-[10px] tabular-nums text-[#858189]">
          {pct.toFixed(0)}% utilized
        </span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<TradingStats | null>(null);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [openPos, setOpenPos] = useState<Position[]>([]);

  async function load() {
    const [s, d, sig, a, o] = await Promise.all([
      getStats(),
      getRecentDecisions(50),
      getRecentSignals(60),
      getRecentAnalyses(10),
      getOpenPositions(),
    ]);
    setStats(s);
    setDecisions(d);
    setSignals(sig);
    setAnalyses(a);
    setOpenPos(o);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);

  const totalSignals = decisions.reduce((s, d) => s + d.signals_detected, 0);
  const totalAnalyses = decisions.reduce((s, d) => s + d.analyses_produced, 0);
  const totalTrades = decisions.reduce((s, d) => s + d.trades_executed, 0);
  const pipelineCounts = [
    totalSignals,
    totalAnalyses,
    totalAnalyses,
    totalTrades,
    openPos.length,
  ];

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1
            className="text-2xl font-bold text-white tracking-tight"
            style={{ fontFamily: "'Sora', sans-serif" }}
          >
            Command Center
          </h1>
          <p
            className="text-sm text-[#858189] mt-1"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            Real-time agent pipeline monitoring and market intelligence
          </p>
        </div>
        <div className="flex items-center gap-2.5 px-4 py-2 bg-[#84f593]/8 border border-[#84f593]/20 rounded-full backdrop-blur-sm">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#84f593] opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#84f593]" />
          </span>
          <span
            className="text-xs font-semibold uppercase tracking-wider text-[#84f593]"
            style={{ fontFamily: "'Sora', sans-serif" }}
          >
            Live
          </span>
        </div>
      </div>

      {/* Pipeline Status */}
      <section>
        <h2
          className="text-[11px] font-semibold uppercase tracking-widest text-[#858189] mb-3"
          style={{ fontFamily: "'Sora', sans-serif" }}
        >
          Pipeline Status
        </h2>
        <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-5 hover:border-[#656169] transition-colors">
          <div className="flex items-center">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={step.label} className="flex items-center flex-1">
                <div className="flex-1 text-center">
                  <div
                    className="text-2xl font-bold tabular-nums text-white"
                    style={{ fontFamily: "'Sora', sans-serif" }}
                  >
                    {pipelineCounts[i]}
                  </div>
                  <div
                    className="text-[10px] font-semibold uppercase tracking-widest text-[#bfa1f5] mt-1"
                    style={{ fontFamily: "'Sora', sans-serif" }}
                  >
                    {step.label}
                  </div>
                  <div
                    className="text-[9px] text-[#858189] mt-0.5"
                    style={{ fontFamily: "'Inter', sans-serif" }}
                  >
                    {step.sublabel}
                  </div>
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <div className="flex-shrink-0 mx-1">
                    <svg
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      className="text-[#8239ef] opacity-60"
                    >
                      <path
                        d="M5 12h14m-4-4 4 4-4 4"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Key Metrics */}
      {stats && (
        <section>
          <h2
            className="text-[11px] font-semibold uppercase tracking-widest text-[#858189] mb-3"
            style={{ fontFamily: "'Sora', sans-serif" }}
          >
            Key Metrics
          </h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <MetricCard
              label="Total PnL"
              value={`${stats.total_pnl >= 0 ? "+" : ""}$${stats.total_pnl.toFixed(2)}`}
              delta={`${stats.total_pnl >= 0 ? "+" : ""}${((stats.total_pnl / 100) * 100).toFixed(1)}% return`}
              deltaColor={
                stats.total_pnl >= 0 ? "text-[#84f593]" : "text-[#f2685f]"
              }
            />
            <MetricCard
              label="Win Rate"
              value={`${stats.win_rate.toFixed(1)}%`}
              delta={`${stats.wins}W / ${stats.closed_trades - stats.wins}L of ${stats.closed_trades} closed`}
              deltaColor={
                stats.win_rate >= 50 ? "text-[#84f593]" : "text-[#f2685f]"
              }
            />
            <MetricCard
              label="Open Positions"
              value={`${openPos.length}`}
              delta={`of 5 max (${((openPos.length / 5) * 100).toFixed(0)}% capacity)`}
              deltaColor={
                openPos.length >= 4 ? "text-[#F59E0B]" : "text-[#858189]"
              }
            />
            <MetricCard
              label="Exposure"
              value={`$${stats.open_exposure.toFixed(0)}`}
              delta={`of $1,000 limit (${((stats.open_exposure / 1000) * 100).toFixed(0)}% utilized)`}
              deltaColor={
                stats.open_exposure >= 800
                  ? "text-[#f2685f]"
                  : stats.open_exposure >= 500
                    ? "text-[#F59E0B]"
                    : "text-[#858189]"
              }
            />
          </div>
        </section>
      )}

      {/* Boba API Connections */}
      <section>
        <h2
          className="text-[11px] font-semibold uppercase tracking-widest text-[#858189] mb-3"
          style={{ fontFamily: "'Sora', sans-serif" }}
        >
          Boba API Connections
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {BOBA_TOOLS.map((t) => (
            <div
              key={t.name}
              className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-4 transition-all hover:border-[#656169] hover:bg-[#2e2d32] group"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-lg bg-[#8239ef]/10 text-[#bfa1f5] group-hover:bg-[#8239ef]/20 transition-colors">
                  {t.icon}
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#84f593] opacity-40" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-[#84f593]" />
                  </span>
                  <span
                    className="text-[10px] font-medium uppercase tracking-wide text-[#84f593]"
                    style={{ fontFamily: "'Inter', sans-serif" }}
                  >
                    Active
                  </span>
                </div>
              </div>
              <h3
                className="text-sm font-semibold text-white mb-1"
                style={{ fontFamily: "'Sora', sans-serif" }}
              >
                {t.name}
              </h3>
              <code className="text-[11px] text-[#bfa1f5] font-mono bg-[#1e1d21] px-1.5 py-0.5 rounded">
                {t.prefix}
              </code>
              <p
                className="text-xs text-[#858189] mt-2 leading-relaxed"
                style={{ fontFamily: "'Inter', sans-serif" }}
              >
                {t.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Risk Utilization */}
      {stats && (
        <section>
          <h2
            className="text-[11px] font-semibold uppercase tracking-widest text-[#858189] mb-3"
            style={{ fontFamily: "'Sora', sans-serif" }}
          >
            Risk Utilization
          </h2>
          <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-5 hover:border-[#656169] transition-colors">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <ProgressBar
                label="Portfolio Exposure"
                value={stats.open_exposure}
                max={1000}
                color="#8239ef"
              />
              <ProgressBar
                label="Open Positions"
                value={openPos.length}
                max={5}
                color="#bfa1f5"
              />
            </div>
          </div>
        </section>
      )}

      {/* Two-column: Recent Signals + AI Reasoning */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Signals */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2
              className="text-[11px] font-semibold uppercase tracking-widest text-[#858189]"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              Recent Signals
            </h2>
            <span className="text-[10px] text-[#858189] tabular-nums">
              {signals.length} detected
            </span>
          </div>
          {signals.length === 0 ? (
            <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-10 text-center">
              <div className="text-[#656169] mb-2">
                <svg
                  width="32"
                  height="32"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  className="mx-auto"
                >
                  <path
                    d="M22 12h-4l-3 9L9 3l-3 9H2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <p
                className="text-sm text-[#858189]"
                style={{ fontFamily: "'Inter', sans-serif" }}
              >
                No signals detected recently
              </p>
              <p
                className="text-xs text-[#656169] mt-1"
                style={{ fontFamily: "'Inter', sans-serif" }}
              >
                The agent is actively scanning markets...
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1 scrollbar-thin">
              {signals.slice(0, 8).map((s) => (
                <SignalCard key={s.id} signal={s} />
              ))}
            </div>
          )}
        </section>

        {/* AI Reasoning */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2
              className="text-[11px] font-semibold uppercase tracking-widest text-[#858189]"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              AI Reasoning
            </h2>
            <span className="text-[10px] text-[#858189] tabular-nums">
              {analyses.length} analyses
            </span>
          </div>
          {analyses.length === 0 ? (
            <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-10 text-center">
              <div className="text-[#656169] mb-2">
                <svg
                  width="32"
                  height="32"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  className="mx-auto"
                >
                  <path
                    d="M12 2a10 10 0 1 0 10 10"
                    strokeLinecap="round"
                  />
                  <path
                    d="M12 6v6l4 2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <p
                className="text-sm text-[#858189]"
                style={{ fontFamily: "'Inter', sans-serif" }}
              >
                No analyses yet
              </p>
              <p
                className="text-xs text-[#656169] mt-1"
                style={{ fontFamily: "'Inter', sans-serif" }}
              >
                Waiting for signals to analyze...
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1 scrollbar-thin">
              {analyses.slice(0, 8).map((a) => (
                <details
                  key={a.id}
                  className="bg-[#28272b] border border-[#3c3a41] rounded-xl transition-all hover:border-[#656169] group"
                >
                  <summary className="cursor-pointer p-4 flex items-center justify-between text-sm list-none [&::-webkit-details-marker]:hidden">
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`text-[11px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-md ${
                          a.suggested_direction === "long"
                            ? "bg-[#84f593]/10 text-[#84f593] border border-[#84f593]/20"
                            : "bg-[#f2685f]/10 text-[#f2685f] border border-[#f2685f]/20"
                        }`}
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
                        className={`text-[11px] font-semibold px-2 py-0.5 rounded-md ${
                          a.conviction_score >= 0.7
                            ? "bg-[#bfa1f5]/10 text-[#bfa1f5] border border-[#bfa1f5]/20"
                            : a.conviction_score >= 0.4
                              ? "bg-[#F59E0B]/10 text-[#F59E0B] border border-[#F59E0B]/20"
                              : "bg-[#858189]/10 text-[#858189] border border-[#858189]/20"
                        }`}
                      >
                        {(a.conviction_score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-[#b8b5bb] tabular-nums font-medium">
                        ${a.suggested_size_usd.toFixed(0)}
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
                    <p
                      className="text-sm text-[#b8b5bb] mt-3 leading-relaxed"
                      style={{ fontFamily: "'Inter', sans-serif" }}
                    >
                      {a.reasoning}
                    </p>
                    {a.risk_notes && (
                      <div className="mt-3 flex items-start gap-2 bg-[#F59E0B]/5 border border-[#F59E0B]/15 rounded-lg px-3 py-2">
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
                          className="text-xs text-[#F59E0B]"
                          style={{ fontFamily: "'Inter', sans-serif" }}
                        >
                          {a.risk_notes}
                        </p>
                      </div>
                    )}
                    <div className="mt-3 text-[10px] text-[#858189] tabular-nums">
                      {new Date(a.created_at).toLocaleString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </div>
                  </div>
                </details>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
