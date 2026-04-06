"use client";

import { useEffect, useState, useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from "recharts";
import MetricCard from "@/components/metric-card";
import SignalCard from "@/components/signal-card";
import { getRecentSignals, getRecentAnalyses } from "@/lib/queries";
import { COLORS } from "@/lib/colors";
import type { Signal, Analysis } from "@/lib/types";

const TIME_OPTIONS = [
  { value: 30, label: "30m" },
  { value: 60, label: "1h" },
  { value: 360, label: "6h" },
  { value: 1440, label: "24h" },
];

function convictionBadge(score: number) {
  if (score >= 0.7) return "bg-sf-up/10 text-sf-up";
  if (score >= 0.4) return "bg-sf-warn/10 text-sf-warn";
  return "bg-sf-down/10 text-sf-down";
}

export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [minutes, setMinutes] = useState(60);
  const [category, setCategory] = useState("All");

  async function load() {
    const [s, a] = await Promise.all([
      getRecentSignals(minutes),
      getRecentAnalyses(200),
    ]);
    setSignals(s);
    setAnalyses(a);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, [minutes]);

  const analysisMap = new Map(analyses.map((a) => [a.signal_id, a]));
  const categories = useMemo(() => [...new Set(signals.map((s) => s.category))].sort(), [signals]);
  const filteredSignals = category === "All" ? signals : signals.filter((s) => s.category === category);
  const withAnalysis = filteredSignals.filter((s) => analysisMap.has(s.id));
  const avgChange =
    filteredSignals.length > 0
      ? filteredSignals.reduce((s, sig) => s + Math.abs(sig.price_change_pct), 0) / filteredSignals.length
      : 0;

  // Category breakdown for bar chart
  const categoryBreakdown = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of signals) counts[s.category] = (counts[s.category] ?? 0) + 1;
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([name, count]) => ({ name, count }));
  }, [signals]);

  // Price change distribution histogram
  const histogram = useMemo(() => {
    if (filteredSignals.length === 0) return [];
    const changes = filteredSignals.map((s) => s.price_change_pct * 100);
    const min = Math.min(...changes);
    const max = Math.max(...changes);
    const bins = 20;
    const step = (max - min) / bins || 1;
    const buckets: { range: string; count: number; mid: number }[] = [];
    for (let i = 0; i < bins; i++) {
      const lo = min + i * step;
      const hi = lo + step;
      const count = changes.filter((c) => c >= lo && (i === bins - 1 ? c <= hi : c < hi)).length;
      buckets.push({ range: `${lo.toFixed(1)}%`, count, mid: (lo + hi) / 2 });
    }
    return buckets;
  }, [filteredSignals]);

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-[1200px]">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-sf-text">Market Scanner</h1>
          <p className="text-sm text-sf-muted mt-0.5">
            Real-time Polymarket, KOL, and funding rate monitoring.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Category Filter */}
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="bg-sf-card border border-sf-border rounded-lg px-3 py-1.5 text-xs text-sf-text focus:outline-none focus:border-sf-brand"
          >
            <option value="All">All Categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          {/* Time Filter */}
          <div className="flex bg-sf-card border border-sf-border rounded-lg overflow-hidden">
            {TIME_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setMinutes(opt.value)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  minutes === opt.value
                    ? "bg-sf-brand/15 text-sf-brand"
                    : "text-sf-muted hover:text-sf-text-2 hover:bg-white/[0.03]"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard label="Signals" value={String(filteredSignals.length)} delta={`in last ${minutes >= 60 ? `${minutes / 60}h` : `${minutes}m`}`} />
        <MetricCard label="Categories" value={String(categories.length)} delta={categories.slice(0, 2).join(", ") || "none"} />
        <MetricCard
          label="Avg |Change|"
          value={`${(avgChange * 100).toFixed(1)}%`}
          delta="across filtered signals"
        />
        <MetricCard
          label="With Analysis"
          value={String(withAnalysis.length)}
          delta={`${filteredSignals.length > 0 ? ((withAnalysis.length / filteredSignals.length) * 100).toFixed(0) : 0}% coverage`}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Signal Type Breakdown */}
        {categoryBreakdown.length > 0 && (
          <section className="bg-sf-card border border-sf-border rounded-lg">
            <div className="p-4 border-b border-sf-border">
              <h2 className="text-sm font-semibold text-sf-text">Signal Type Breakdown</h2>
            </div>
            <div className="p-4">
              <ResponsiveContainer width="100%" height={Math.max(200, categoryBreakdown.length * 32)}>
                <BarChart data={categoryBreakdown} layout="vertical">
                  <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tick={{ fill: COLORS.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" tick={{ fill: COLORS.text2, fontSize: 11 }} axisLine={false} tickLine={false} width={120} />
                  <Tooltip contentStyle={{ background: COLORS.card, border: `1px solid ${COLORS.borderBold}`, borderRadius: 8, color: COLORS.text, fontSize: 12 }} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {categoryBreakdown.map((_, i) => (
                      <Cell key={i} fill={COLORS.brand} opacity={0.7} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {/* Price Change Distribution */}
        {histogram.length > 0 && (
          <section className="bg-sf-card border border-sf-border rounded-lg">
            <div className="p-4 border-b border-sf-border">
              <h2 className="text-sm font-semibold text-sf-text">Price Change Distribution</h2>
              <p className="text-xs text-sf-muted mt-0.5">Where market moves cluster</p>
            </div>
            <div className="p-4">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={histogram}>
                  <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="range" tick={{ fill: COLORS.muted, fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fill: COLORS.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: COLORS.card, border: `1px solid ${COLORS.borderBold}`, borderRadius: 8, color: COLORS.text, fontSize: 12 }} />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {histogram.map((b, i) => (
                      <Cell key={i} fill={b.mid >= 0 ? COLORS.up : COLORS.down} opacity={0.6} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}
      </div>

      {/* Signal Feed */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">
          Signal Feed ({filteredSignals.length})
        </h2>
        {filteredSignals.length === 0 ? (
          <div className="bg-sf-card border border-sf-border rounded-lg p-12 text-center">
            <svg className="w-8 h-8 text-sf-subtle mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M2 12h2M6 8v8M10 4v16M14 6v12M18 10v4M22 12h-2" strokeLinecap="round" />
            </svg>
            <p className="text-sm text-sf-muted">No signals match the current filters.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredSignals.map((s) => {
              const analysis = analysisMap.get(s.id);
              return (
                <div key={s.id}>
                  <SignalCard signal={s} />
                  {analysis && (
                    <div className="ml-4 mt-1 border-l-2 border-sf-brand/20 rounded-r-lg bg-sf-card/60 p-2.5 text-xs">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`font-semibold px-1.5 py-0.5 rounded text-[10px] ${
                          analysis.suggested_direction === "long"
                            ? "bg-sf-up/10 text-sf-up"
                            : "bg-sf-down/10 text-sf-down"
                        }`}>
                          {analysis.suggested_direction.toUpperCase()}
                        </span>
                        <span className="text-sf-text-2 font-medium">{analysis.suggested_asset}</span>
                        <span className={`font-semibold px-1.5 py-0.5 rounded text-[10px] ${convictionBadge(analysis.conviction_score)}`}>
                          {(analysis.conviction_score * 100).toFixed(0)}%
                        </span>
                        <span className="text-sf-muted tabular-nums">${analysis.suggested_size_usd.toFixed(0)}</span>
                      </div>
                      <p className="text-sf-muted mt-1.5 leading-relaxed line-clamp-2">
                        {analysis.reasoning}
                      </p>
                      {analysis.risk_notes && (
                        <p className="text-sf-warn mt-1 flex items-center gap-1">
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v4m0 4h.01M10.29 3.86l-8.7 15.04A1 1 0 0 0 2.46 21h19.08a1 1 0 0 0 .87-1.5l-8.7-15.04a1.35 1.35 0 0 0-2.42 0z" /></svg>
                          {analysis.risk_notes}
                        </p>
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
