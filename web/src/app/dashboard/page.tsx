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
  { name: "Polymarket Scanner", prefix: "pm_*", desc: "Prediction market price moves that may signal real-world events." },
  { name: "KOL Wallet Tracker", prefix: "get_kol*", desc: "Whale and influencer wallets for smart-money positioning." },
  { name: "Funding Rate Monitor", prefix: "hl_funding*", desc: "Perpetual swap funding rates to detect crowded positions." },
  { name: "Cross-Chain Arb", prefix: "crosschain_*", desc: "Token price comparison across chains for mispricing." },
];

const PIPELINE_STEPS = ["Triggers", "Analyzer", "Risk Gate", "Executor", "Manager"];

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
  const pipelineCounts = [totalSignals, totalAnalyses, totalAnalyses, totalTrades, openPos.length];

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-[1200px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-sf-text">Command Center</h1>
          <p className="text-sm text-sf-muted mt-0.5">
            Real-time agent pipeline monitoring and market intelligence.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-sf-up/10 border border-sf-up/20 rounded-full">
          <div className="w-1.5 h-1.5 rounded-full bg-sf-up animate-pulse" />
          <span className="text-xs font-medium text-sf-up">Live</span>
        </div>
      </div>

      {/* Pipeline Status */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">Pipeline</h2>
        <div className="bg-sf-card border border-sf-border rounded-lg p-4">
          <div className="flex items-center gap-2">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={step} className="flex items-center gap-2 flex-1">
                <div className="flex-1 text-center">
                  <div className="text-lg font-semibold tabular-nums text-sf-text">{pipelineCounts[i]}</div>
                  <div className="text-[10px] font-medium uppercase tracking-wider text-sf-muted mt-0.5">{step}</div>
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-sf-subtle flex-shrink-0">
                    <path d="m9 18 6-6-6-6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Key Metrics */}
      {stats && (
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">Metrics</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricCard
              label="Total PnL"
              value={`$${stats.total_pnl.toFixed(2)}`}
              delta={`${stats.total_pnl >= 0 ? "+" : ""}$${stats.total_pnl.toFixed(2)}`}
              deltaColor={stats.total_pnl >= 0 ? "text-sf-up" : "text-sf-down"}
            />
            <MetricCard
              label="Win Rate"
              value={`${stats.win_rate.toFixed(1)}%`}
              delta={`${stats.wins}W / ${stats.closed_trades - stats.wins}L`}
            />
            <MetricCard
              label="Open Positions"
              value={String(openPos.length)}
              delta="of 5 max"
            />
            <MetricCard
              label="Exposure"
              value={`$${stats.open_exposure.toFixed(0)}`}
              delta="of $1,000 limit"
            />
          </div>
        </section>
      )}

      {/* Boba API Connections */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">Boba API Connections</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {BOBA_TOOLS.map((t) => (
            <div key={t.name} className="bg-sf-card border border-sf-border rounded-lg p-4 transition-colors hover:border-sf-border-bold">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-sf-up" />
                <span className="text-sm font-medium text-sf-text">{t.name}</span>
              </div>
              <code className="text-xs text-sf-brand font-mono">{t.prefix}</code>
              <p className="text-xs text-sf-muted mt-1.5 leading-relaxed">{t.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Signals + AI Reasoning grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Signals */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">
            Recent Signals
          </h2>
          {signals.length === 0 ? (
            <div className="bg-sf-card border border-sf-border rounded-lg p-8 text-center">
              <p className="text-sm text-sf-muted">No signals detected recently.</p>
              <p className="text-xs text-sf-subtle mt-1">The agent is scanning markets...</p>
            </div>
          ) : (
            <div className="space-y-2">
              {signals.slice(0, 8).map((s) => (
                <SignalCard key={s.id} signal={s} />
              ))}
            </div>
          )}
        </section>

        {/* AI Reasoning */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">
            AI Reasoning
          </h2>
          {analyses.length === 0 ? (
            <div className="bg-sf-card border border-sf-border rounded-lg p-8 text-center">
              <p className="text-sm text-sf-muted">No analyses yet.</p>
              <p className="text-xs text-sf-subtle mt-1">Waiting for signals...</p>
            </div>
          ) : (
            <div className="space-y-2">
              {analyses.slice(0, 6).map((a) => (
                <details
                  key={a.id}
                  className="bg-sf-card border border-sf-border rounded-lg transition-colors hover:border-sf-border-bold group"
                >
                  <summary className="cursor-pointer p-3 flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                        a.suggested_direction === "long"
                          ? "bg-sf-up/10 text-sf-up"
                          : "bg-sf-down/10 text-sf-down"
                      }`}>
                        {a.suggested_direction.toUpperCase()}
                      </span>
                      <span className="font-medium text-sf-text">{a.suggested_asset}</span>
                      <span className="text-sf-muted text-xs">
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
                    <p className="text-sm text-sf-text-2 mt-3 leading-relaxed">
                      {a.reasoning}
                    </p>
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
          )}
        </section>
      </div>
    </div>
  );
}
