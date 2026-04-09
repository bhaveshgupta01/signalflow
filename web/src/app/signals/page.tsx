"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from "recharts";
import MetricCard from "@/components/metric-card";
import { getRecentSignals, getRecentAnalyses } from "@/lib/queries";
import { COLORS } from "@/lib/colors";
import type { Signal, Analysis } from "@/lib/types";

const TIME_OPTIONS = [
  { value: 60, label: "1H" },
  { value: 360, label: "6H" },
  { value: 1440, label: "24H" },
  { value: 525600, label: "ALL" },
];

function convictionBadge(score: number) {
  if (score >= 0.7) return "bg-[#8239ef]/15 text-[#bfa1f5] border border-[#8239ef]/30";
  if (score >= 0.4) return "bg-[#F59E0B]/10 text-[#F59E0B] border border-[#F59E0B]/30";
  return "bg-[#858189]/10 text-[#858189] border border-[#858189]/30";
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.round(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ${mins % 60}m ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function truncate(s: string, len: number) {
  return s.length > len ? s.slice(0, len) + "..." : s;
}

export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [minutes, setMinutes] = useState(60);
  const [category, setCategory] = useState("All");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const load = useCallback(async () => {
    const [s, a] = await Promise.all([
      getRecentSignals(minutes),
      getRecentAnalyses(500),
    ]);
    setSignals(s);
    setAnalyses(a);
  }, [minutes]);

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, [load]);

  const analysisMap = useMemo(() => new Map(analyses.map((a) => [a.signal_id, a])), [analyses]);
  const categories = useMemo(() => [...new Set(signals.map((s) => s.category))].sort(), [signals]);
  const filteredSignals = useMemo(
    () => category === "All" ? signals : signals.filter((s) => s.category === category),
    [signals, category]
  );
  const withAnalysis = useMemo(
    () => filteredSignals.filter((s) => analysisMap.has(s.id)),
    [filteredSignals, analysisMap]
  );
  const avgChange = useMemo(
    () => filteredSignals.length > 0
      ? filteredSignals.reduce((s, sig) => s + Math.abs(sig.price_change_pct), 0) / filteredSignals.length
      : 0,
    [filteredSignals]
  );

  // Category breakdown - sorted ascending for horizontal bar
  const categoryBreakdown = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of filteredSignals) counts[s.category] = (counts[s.category] ?? 0) + 1;
    return Object.entries(counts)
      .sort((a, b) => a[1] - b[1])
      .map(([name, count]) => ({ name, count }));
  }, [filteredSignals]);

  // Price change distribution histogram - 25 bins
  const histogram = useMemo(() => {
    if (filteredSignals.length === 0) return [];
    const changes = filteredSignals.map((s) => s.price_change_pct * 100);
    const min = Math.min(...changes);
    const max = Math.max(...changes);
    const bins = 25;
    const step = (max - min) / bins || 1;
    const buckets: { range: string; count: number; mid: number }[] = [];
    for (let i = 0; i < bins; i++) {
      const lo = min + i * step;
      const hi = lo + step;
      const count = changes.filter((c) => c >= lo && (i === bins - 1 ? c <= hi : c < hi)).length;
      const mid = (lo + hi) / 2;
      buckets.push({ range: `${mid.toFixed(1)}%`, count, mid });
    }
    return buckets;
  }, [filteredSignals]);

  const timeLabel = minutes >= 525600 ? "all time" : minutes >= 60 ? `${minutes / 60}h` : `${minutes}m`;

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: "'Sora', sans-serif" }}>
            Market Scanner
          </h1>
          <p className="text-sm text-[#858189] mt-1 max-w-md" style={{ fontFamily: "'Inter', sans-serif" }}>
            Real-time Polymarket signal detection with AI analysis overlay. Monitors price movements, sentiment shifts, and category trends.
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {/* Category Filter */}
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="bg-[#28272b] border border-[#3c3a41] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#bfa1f5] transition-colors cursor-pointer appearance-none min-w-[140px]"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            <option value="All">All Categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          {/* Time Filter */}
          <div className="flex bg-[#28272b] border border-[#3c3a41] rounded-xl overflow-hidden">
            {TIME_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setMinutes(opt.value)}
                className={`px-4 py-2 text-xs font-semibold transition-all ${
                  minutes === opt.value
                    ? "bg-[#8239ef]/20 text-[#bfa1f5] shadow-inner"
                    : "text-[#858189] hover:text-[#b8b5bb] hover:bg-white/[0.03]"
                }`}
                style={{ fontFamily: "'Sora', sans-serif" }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Summary Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          label="Total Signals"
          value={String(filteredSignals.length)}
          delta={`in last ${timeLabel}`}
        />
        <MetricCard
          label="Avg |Price Change|"
          value={`${(avgChange * 100).toFixed(2)}%`}
          delta="absolute change across signals"
        />
        <MetricCard
          label="With AI Analysis"
          value={String(withAnalysis.length)}
          delta={`${filteredSignals.length > 0 ? ((withAnalysis.length / filteredSignals.length) * 100).toFixed(0) : 0}% analysis coverage`}
        />
        <MetricCard
          label="Unique Categories"
          value={String(categories.length)}
          delta={categories.slice(0, 3).join(", ") || "none detected"}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Signal Type Breakdown - Horizontal BarChart */}
        <section className="bg-[#28272b] border border-[#3c3a41] rounded-xl hover:border-[#656169] transition-colors">
          <div className="p-4 border-b border-[#3c3a41]">
            <h2 className="text-sm font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>
              Signal Type Breakdown
            </h2>
            <p className="text-xs text-[#858189] mt-0.5" style={{ fontFamily: "'Inter', sans-serif" }}>
              Signal count by market category
            </p>
          </div>
          <div className="p-4">
            {categoryBreakdown.length > 0 ? (
              <ResponsiveContainer width="100%" height={Math.max(180, categoryBreakdown.length * 36)}>
                <BarChart data={categoryBreakdown} layout="vertical" margin={{ left: 10, right: 20, top: 5, bottom: 5 }}>
                  <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fill: COLORS.muted, fontSize: 11, fontFamily: "'Inter', sans-serif" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fill: COLORS.text2, fontSize: 11, fontFamily: "'Inter', sans-serif" }}
                    axisLine={false}
                    tickLine={false}
                    width={130}
                  />
                  <Tooltip
                    contentStyle={{
                      background: COLORS.card,
                      border: `1px solid ${COLORS.borderBold}`,
                      borderRadius: 10,
                      color: COLORS.text,
                      fontSize: 12,
                      fontFamily: "'Inter', sans-serif",
                      boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
                    }}
                    cursor={{ fill: "rgba(255,255,255,0.03)" }}
                  />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]} maxBarSize={24}>
                    {categoryBreakdown.map((_, i) => (
                      <Cell key={i} fill={COLORS.brand} opacity={0.75} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="py-12 text-center">
                <p className="text-xs text-[#858189]" style={{ fontFamily: "'Inter', sans-serif" }}>No category data available.</p>
              </div>
            )}
          </div>
        </section>

        {/* Price Change Distribution - Histogram */}
        <section className="bg-[#28272b] border border-[#3c3a41] rounded-xl hover:border-[#656169] transition-colors">
          <div className="p-4 border-b border-[#3c3a41]">
            <h2 className="text-sm font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>
              Price Change Distribution
            </h2>
            <p className="text-xs text-[#858189] mt-0.5" style={{ fontFamily: "'Inter', sans-serif" }}>
              Where market price movements cluster (red = negative, green = positive)
            </p>
          </div>
          <div className="p-4">
            {histogram.length > 0 ? (
              <ResponsiveContainer width="100%" height={Math.max(180, categoryBreakdown.length * 36)}>
                <BarChart data={histogram} margin={{ left: 0, right: 10, top: 5, bottom: 5 }}>
                  <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="range"
                    tick={{ fill: COLORS.muted, fontSize: 9, fontFamily: "'Inter', sans-serif" }}
                    axisLine={false}
                    tickLine={false}
                    interval={Math.max(0, Math.floor(histogram.length / 6))}
                  />
                  <YAxis
                    tick={{ fill: COLORS.muted, fontSize: 11, fontFamily: "'Inter', sans-serif" }}
                    axisLine={false}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: COLORS.card,
                      border: `1px solid ${COLORS.borderBold}`,
                      borderRadius: 10,
                      color: COLORS.text,
                      fontSize: 12,
                      fontFamily: "'Inter', sans-serif",
                      boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
                    }}
                    cursor={{ fill: "rgba(255,255,255,0.03)" }}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={20}>
                    {histogram.map((b, i) => (
                      <Cell key={i} fill={b.mid >= 0 ? COLORS.up : COLORS.down} opacity={0.65} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="py-12 text-center">
                <p className="text-xs text-[#858189]" style={{ fontFamily: "'Inter', sans-serif" }}>No price data to chart.</p>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Signal Feed */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[#858189]" style={{ fontFamily: "'Sora', sans-serif" }}>
            Signal Feed
          </h2>
          <span className="text-xs text-[#656169] tabular-nums" style={{ fontFamily: "'Inter', sans-serif" }}>
            {filteredSignals.length} signal{filteredSignals.length !== 1 ? "s" : ""}
          </span>
        </div>

        {filteredSignals.length === 0 ? (
          <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-16 text-center">
            <svg className="w-10 h-10 text-[#656169] mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M2 12h2M6 8v8M10 4v16M14 6v12M18 10v4M22 12h-2" strokeLinecap="round" />
            </svg>
            <p className="text-sm text-[#858189]" style={{ fontFamily: "'Inter', sans-serif" }}>No signals match the current filters.</p>
            <p className="text-xs text-[#656169] mt-1" style={{ fontFamily: "'Inter', sans-serif" }}>Try expanding the time range or category.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredSignals.map((s) => {
              const analysis = analysisMap.get(s.id);
              const isExpanded = expandedId === s.id;
              const positive = s.price_change_pct >= 0;
              const changeColor = positive ? "text-[#84f593]" : "text-[#f2685f]";
              const sign = positive ? "+" : "";

              return (
                <div key={s.id}>
                  {/* Collapsed / Summary Row */}
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : s.id)}
                    className={`w-full text-left bg-[#28272b] border rounded-xl p-3.5 transition-all group ${
                      isExpanded
                        ? "border-[#656169] bg-[#2e2d32] rounded-b-none"
                        : "border-[#3c3a41] hover:border-[#656169] hover:bg-[#2e2d32]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <span className="text-sm text-[#b8b5bb] group-hover:text-white transition-colors truncate" style={{ fontFamily: "'Inter', sans-serif" }}>
                          {truncate(s.market_question, 60)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2.5 flex-shrink-0">
                        <span className={`text-xs font-semibold tabular-nums ${changeColor}`}>
                          {sign}{(s.price_change_pct * 100).toFixed(1)}%
                        </span>
                        <span className="px-2 py-0.5 rounded-full bg-[#1e1d21] text-[#858189] text-[10px] uppercase tracking-wide border border-[#3c3a41]">
                          {s.category}
                        </span>
                        <span className="text-[11px] text-[#656169] tabular-nums w-16 text-right" style={{ fontFamily: "'Inter', sans-serif" }}>
                          {timeAgo(s.detected_at)}
                        </span>
                        {analysis && (
                          <span className="w-1.5 h-1.5 rounded-full bg-[#bfa1f5] flex-shrink-0" title="Has AI analysis" />
                        )}
                        <svg
                          className={`w-3.5 h-3.5 text-[#656169] transition-transform ${isExpanded ? "rotate-180" : ""}`}
                          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                        >
                          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </div>
                    </div>
                  </button>

                  {/* Expanded Detail */}
                  {isExpanded && (
                    <div className="bg-[#2e2d32] border border-t-0 border-[#656169] rounded-b-xl overflow-hidden">
                      {/* Signal Details */}
                      <div className="p-4 border-b border-[#3c3a41]">
                        <p className="text-sm text-white leading-relaxed mb-3" style={{ fontFamily: "'Inter', sans-serif" }}>
                          {s.market_question}
                        </p>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                          <div>
                            <div className="text-[10px] uppercase tracking-wider text-[#656169] mb-0.5" style={{ fontFamily: "'Sora', sans-serif" }}>Current Price</div>
                            <div className="text-sm font-medium text-white tabular-nums">{s.current_price.toFixed(4)}</div>
                          </div>
                          <div>
                            <div className="text-[10px] uppercase tracking-wider text-[#656169] mb-0.5" style={{ fontFamily: "'Sora', sans-serif" }}>Price Change</div>
                            <div className={`text-sm font-semibold tabular-nums ${changeColor}`}>
                              {sign}{(s.price_change_pct * 100).toFixed(2)}%
                            </div>
                          </div>
                          <div>
                            <div className="text-[10px] uppercase tracking-wider text-[#656169] mb-0.5" style={{ fontFamily: "'Sora', sans-serif" }}>Category</div>
                            <div className="text-sm text-[#b8b5bb]">{s.category}</div>
                          </div>
                          <div>
                            <div className="text-[10px] uppercase tracking-wider text-[#656169] mb-0.5" style={{ fontFamily: "'Sora', sans-serif" }}>Detected</div>
                            <div className="text-sm text-[#b8b5bb]" style={{ fontFamily: "'Inter', sans-serif" }}>
                              {new Date(s.detected_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* AI Analysis (if exists) */}
                      {analysis && (
                        <div className="p-4 bg-[#28272b]/50">
                          <div className="flex items-center gap-2 mb-2.5">
                            <svg className="w-3.5 h-3.5 text-[#bfa1f5]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.27 5.82 22 7 14.14l-5-4.87 6.91-1.01L12 2z" />
                            </svg>
                            <span className="text-xs font-semibold text-[#bfa1f5] uppercase tracking-wider" style={{ fontFamily: "'Sora', sans-serif" }}>
                              AI Analysis
                            </span>
                          </div>
                          <div className="flex items-center gap-2 flex-wrap mb-3">
                            <span className={`text-xs font-bold px-2 py-1 rounded-lg ${
                              analysis.suggested_direction === "long"
                                ? "bg-[#84f593]/10 text-[#84f593]"
                                : "bg-[#f2685f]/10 text-[#f2685f]"
                            }`}>
                              {analysis.suggested_direction.toUpperCase()}
                            </span>
                            <span className="text-sm font-medium text-white">{analysis.suggested_asset}</span>
                            <span className={`text-xs font-bold px-2 py-1 rounded-lg ${convictionBadge(analysis.conviction_score)}`}>
                              {(analysis.conviction_score * 100).toFixed(0)}% conviction
                            </span>
                            <span className="text-xs text-[#858189] tabular-nums">${analysis.suggested_size_usd.toFixed(0)} size</span>
                          </div>
                          <p className="text-xs text-[#b8b5bb] leading-relaxed" style={{ fontFamily: "'Inter', sans-serif" }}>
                            {analysis.reasoning}
                          </p>
                          {analysis.risk_notes && (
                            <div className="mt-2.5 flex items-start gap-1.5 text-xs text-[#F59E0B]">
                              <svg className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M12 9v4m0 4h.01M10.29 3.86l-8.7 15.04A1 1 0 0 0 2.46 21h19.08a1 1 0 0 0 .87-1.5l-8.7-15.04a1.35 1.35 0 0 0-2.42 0z" />
                              </svg>
                              <span className="leading-relaxed" style={{ fontFamily: "'Inter', sans-serif" }}>{analysis.risk_notes}</span>
                            </div>
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
