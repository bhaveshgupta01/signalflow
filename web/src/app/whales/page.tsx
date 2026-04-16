"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
  ScatterChart, Scatter,
} from "recharts";
import MetricCard from "@/components/metric-card";
import { getAllKolSignals, getRecentSignals } from "@/lib/queries";
import { COLORS, getAssetColor } from "@/lib/colors";
import type { KolSignal, Signal } from "@/lib/types";

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

function formatUsd(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function WhalesPage() {
  const [kols, setKols] = useState<KolSignal[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const load = useCallback(async () => {
    const [k, s] = await Promise.all([
      getAllKolSignals(500),
      getRecentSignals(525600),
    ]);
    setKols(k);
    setSignals(s);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, [load]);

  // Derived stats
  const uniqueKols = useMemo(() => new Set(kols.map((k) => k.kol_name)), [kols]);
  const totalVolume = useMemo(() => kols.reduce((s, k) => s + k.trade_size_usd, 0), [kols]);

  // Volume by asset - sorted ascending for horizontal bar
  const volumeByAsset = useMemo(() => {
    const m: Record<string, number> = {};
    for (const k of kols) m[k.asset] = (m[k.asset] ?? 0) + k.trade_size_usd;
    return Object.entries(m)
      .sort((a, b) => a[1] - b[1])
      .map(([asset, volume]) => ({ asset, volume }));
  }, [kols]);

  // Most active asset
  const topAsset = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const k of kols) counts[k.asset] = (counts[k.asset] ?? 0) + 1;
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return sorted[0] ?? null;
  }, [kols]);

  // Most active KOL
  const topKol = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const k of kols) counts[k.kol_name] = (counts[k.kol_name] ?? 0) + 1;
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return sorted[0] ?? null;
  }, [kols]);

  // Activity timeline scatter data
  const longTrades = useMemo(() =>
    kols.filter((k) => k.direction === "long").map((k) => ({
      time: new Date(k.detected_at).getTime(),
      size: k.trade_size_usd,
      name: k.kol_name,
      asset: k.asset,
    })),
    [kols]
  );
  const shortTrades = useMemo(() =>
    kols.filter((k) => k.direction === "short").map((k) => ({
      time: new Date(k.detected_at).getTime(),
      size: k.trade_size_usd,
      name: k.kol_name,
      asset: k.asset,
    })),
    [kols]
  );

  // Signal correlation
  const correlations = useMemo(() => {
    return kols.map((k) => {
      const matchingSignal = signals.find(
        (s) =>
          s.market_question.toLowerCase().includes(k.asset.toLowerCase()) ||
          s.category.toLowerCase().includes(k.asset.toLowerCase())
      );
      const hasMatch = !!matchingSignal;
      let aligned: "Yes" | "No" | "N/A" = "N/A";
      if (matchingSignal) {
        const signalDir = matchingSignal.price_change_pct >= 0 ? "long" : "short";
        aligned = signalDir === k.direction ? "Yes" : "No";
      }
      return {
        id: k.id,
        kol: k.kol_name,
        asset: k.asset,
        direction: k.direction,
        size: k.trade_size_usd,
        polymarketMatch: hasMatch ? "Yes" as const : "No" as const,
        aligned,
      };
    });
  }, [kols, signals]);

  const avgTradeSize = kols.length > 0 ? totalVolume / kols.length : 0;

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: "'Sora', sans-serif" }}>
          Whale Intelligence
        </h1>
        <p className="text-sm text-[#858189] mt-1 max-w-lg" style={{ fontFamily: "'Inter', sans-serif" }}>
          Tracking KOL wallets and smart-money flows. When whale activity aligns with Polymarket signals, the agent boosts conviction by 15%.
        </p>
      </div>

      {/* Summary Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          label="Total KOL Signals"
          value={String(kols.length)}
          delta="whale trades detected"
        />
        <MetricCard
          label="Unique Whales"
          value={String(uniqueKols.size)}
          delta="wallets tracked"
        />
        <MetricCard
          label="Most Active Asset"
          value={topAsset ? topAsset[0] : "\u2014"}
          delta={topAsset ? `${topAsset[1]} trades` : ""}
        />
        <MetricCard
          label="Total Volume Tracked"
          value={formatUsd(totalVolume)}
          delta={`across ${volumeByAsset.length} assets`}
        />
      </div>

      {/* Two-column: Volume by Asset + Activity Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Volume by Asset - Horizontal BarChart */}
        <section className="bg-[#28272b] border border-[#3c3a41] rounded-xl hover:border-[#656169] transition-colors">
          <div className="p-4 border-b border-[#3c3a41]">
            <h2 className="text-sm font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>Volume by Asset</h2>
            <p className="text-xs text-[#858189] mt-0.5" style={{ fontFamily: "'Inter', sans-serif" }}>Total KOL trading volume per asset (sorted ascending)</p>
          </div>
          <div className="p-4">
            {volumeByAsset.length > 0 ? (
              <ResponsiveContainer width="100%" height={Math.max(200, volumeByAsset.length * 36)}>
                <BarChart data={volumeByAsset} layout="vertical" margin={{ left: 10, right: 20, top: 5, bottom: 5 }}>
                  <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fill: COLORS.muted, fontSize: 11, fontFamily: "'Inter', sans-serif" }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v: number) => formatUsd(v)}
                  />
                  <YAxis
                    type="category"
                    dataKey="asset"
                    tick={{ fill: COLORS.text2, fontSize: 12, fontFamily: "'Sora', sans-serif", fontWeight: 600 }}
                    axisLine={false}
                    tickLine={false}
                    width={60}
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
                    formatter={(value) => [formatUsd(Number(value)), "Volume"]}
                    cursor={{ fill: "rgba(255,255,255,0.03)" }}
                  />
                  <Bar dataKey="volume" radius={[0, 6, 6, 0]} maxBarSize={24}>
                    {volumeByAsset.map((d, i) => (
                      <Cell key={i} fill={getAssetColor(d.asset)} opacity={0.75} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="py-12 text-center">
                <p className="text-xs text-[#858189]" style={{ fontFamily: "'Inter', sans-serif" }}>No KOL volume data yet.</p>
              </div>
            )}
          </div>
        </section>

        {/* Activity Timeline - ScatterChart */}
        <section className="bg-[#28272b] border border-[#3c3a41] rounded-xl hover:border-[#656169] transition-colors">
          <div className="p-4 border-b border-[#3c3a41]">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>Activity Timeline</h2>
                <p className="text-xs text-[#858189] mt-0.5" style={{ fontFamily: "'Inter', sans-serif" }}>KOL trades over time by size</p>
              </div>
              <div className="flex items-center gap-3 text-[10px]" style={{ fontFamily: "'Inter', sans-serif" }}>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[#84f593]" />
                  <span className="text-[#858189]">Long</span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[#f2685f]" />
                  <span className="text-[#858189]">Short</span>
                </span>
              </div>
            </div>
          </div>
          <div className="p-4">
            {kols.length > 0 ? (
              <ResponsiveContainer width="100%" height={Math.max(200, volumeByAsset.length * 36)}>
                <ScatterChart margin={{ left: 0, right: 10, top: 10, bottom: 5 }}>
                  <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    type="number"
                    domain={["auto", "auto"]}
                    tickFormatter={(v: number) => new Date(v).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    tick={{ fill: COLORS.muted, fontSize: 10, fontFamily: "'Inter', sans-serif" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    dataKey="size"
                    name="Size ($)"
                    tick={{ fill: COLORS.muted, fontSize: 11, fontFamily: "'Inter', sans-serif" }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v: number) => formatUsd(v)}
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
                    labelFormatter={(v) => new Date(Number(v)).toLocaleString()}
                    formatter={(value, name, props) => {
                      const payload = (props as { payload?: { name?: string; asset?: string } }).payload;
                      if (payload?.name) {
                        return [`${payload.name} - ${payload.asset}`, name as string];
                      }
                      return [String(value), name as string];
                    }}
                  />
                  <Scatter name="Long" data={longTrades} fill={COLORS.up} opacity={0.7} />
                  <Scatter name="Short" data={shortTrades} fill={COLORS.down} opacity={0.7} />
                </ScatterChart>
              </ResponsiveContainer>
            ) : (
              <div className="py-16 text-center">
                <p className="text-xs text-[#858189]" style={{ fontFamily: "'Inter', sans-serif" }}>No timeline data yet.</p>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Quick Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-4 hover:border-[#656169] transition-colors">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-[#858189] mb-1.5" style={{ fontFamily: "'Sora', sans-serif" }}>Most Active KOL</div>
          <div className="text-lg font-bold text-white truncate" style={{ fontFamily: "'Sora', sans-serif" }}>{topKol ? topKol[0] : "\u2014"}</div>
          {topKol && <div className="text-xs text-[#858189] mt-0.5" style={{ fontFamily: "'Inter', sans-serif" }}>{topKol[1]} trades</div>}
        </div>
        <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-4 hover:border-[#656169] transition-colors">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-[#858189] mb-1.5" style={{ fontFamily: "'Sora', sans-serif" }}>Avg Trade Size</div>
          <div className="text-lg font-bold text-white tabular-nums" style={{ fontFamily: "'Sora', sans-serif" }}>{formatUsd(avgTradeSize)}</div>
          <div className="text-xs text-[#858189] mt-0.5" style={{ fontFamily: "'Inter', sans-serif" }}>per KOL signal</div>
        </div>
        <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-4 hover:border-[#656169] transition-colors">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-[#858189] mb-1.5" style={{ fontFamily: "'Sora', sans-serif" }}>Conviction Boost</div>
          <div className="text-lg font-bold text-[#bfa1f5]" style={{ fontFamily: "'Sora', sans-serif" }}>+15%</div>
          <div className="text-xs text-[#858189] mt-0.5" style={{ fontFamily: "'Inter', sans-serif" }}>when KOL aligns with signal</div>
        </div>
        <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-4 hover:border-[#656169] transition-colors">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-[#858189] mb-1.5" style={{ fontFamily: "'Sora', sans-serif" }}>Agent Signals</div>
          <div className="text-lg font-bold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>{signals.length}</div>
          <div className="text-xs text-[#858189] mt-0.5" style={{ fontFamily: "'Inter', sans-serif" }}>Polymarket signals detected</div>
        </div>
      </div>

      {/* Signal Correlation Table */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#858189]" style={{ fontFamily: "'Sora', sans-serif" }}>
              Signal Correlation
            </h2>
            <p className="text-xs text-[#656169] mt-0.5" style={{ fontFamily: "'Inter', sans-serif" }}>
              Cross-referencing KOL trades with Polymarket signal directions for conviction boosting.
            </p>
          </div>
          <span className="text-xs text-[#656169] tabular-nums" style={{ fontFamily: "'Inter', sans-serif" }}>
            {correlations.length} entries
          </span>
        </div>
        {correlations.length > 0 ? (
          <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl overflow-hidden hover:border-[#656169] transition-colors">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#3c3a41] bg-[#1e1d21]/60">
                    <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-[#858189]" style={{ fontFamily: "'Sora', sans-serif" }}>KOL Name</th>
                    <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-[#858189]" style={{ fontFamily: "'Sora', sans-serif" }}>Asset</th>
                    <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-[#858189]" style={{ fontFamily: "'Sora', sans-serif" }}>Direction</th>
                    <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-[#858189]" style={{ fontFamily: "'Sora', sans-serif" }}>Trade Size</th>
                    <th className="text-center px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-[#858189]" style={{ fontFamily: "'Sora', sans-serif" }}>Polymarket Match?</th>
                    <th className="text-center px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-[#858189]" style={{ fontFamily: "'Sora', sans-serif" }}>Aligned?</th>
                  </tr>
                </thead>
                <tbody>
                  {correlations.map((c) => (
                    <tr key={c.id} className="border-b border-[#3c3a41]/40 hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-2.5 font-medium text-white text-sm truncate max-w-[160px]" style={{ fontFamily: "'Inter', sans-serif" }}>
                        {c.kol}
                      </td>
                      <td className="px-4 py-2.5 font-semibold text-sm" style={{ color: getAssetColor(c.asset), fontFamily: "'Sora', sans-serif" }}>
                        {c.asset}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md ${
                          c.direction === "long"
                            ? "bg-[#84f593]/10 text-[#84f593]"
                            : "bg-[#f2685f]/10 text-[#f2685f]"
                        }`}>
                          {c.direction.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-[#b8b5bb] text-sm" style={{ fontFamily: "'Inter', sans-serif" }}>
                        {formatUsd(c.size)}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {c.polymarketMatch === "Yes" ? (
                          <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#84f593]">
                            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                            Yes
                          </span>
                        ) : (
                          <span className="text-xs text-[#656169]">No</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-md ${
                          c.aligned === "Yes"
                            ? "bg-[#84f593]/10 text-[#84f593]"
                            : c.aligned === "No"
                            ? "bg-[#f2685f]/10 text-[#f2685f]"
                            : "text-[#656169]"
                        }`}>
                          {c.aligned}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-12 text-center">
            <p className="text-xs text-[#858189]" style={{ fontFamily: "'Inter', sans-serif" }}>No correlation data available yet.</p>
          </div>
        )}
      </section>

      {/* Whale Activity Feed - Expandable */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[#858189]" style={{ fontFamily: "'Sora', sans-serif" }}>
            Whale Activity Feed
          </h2>
          <span className="text-xs text-[#656169] tabular-nums" style={{ fontFamily: "'Inter', sans-serif" }}>
            {kols.length} trade{kols.length !== 1 ? "s" : ""}
          </span>
        </div>

        {kols.length === 0 ? (
          <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-16 text-center">
            <svg className="w-10 h-10 text-[#656169] mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" /><path d="M12 2a14.5 14.5 0 0 0 0 20M12 2a14.5 14.5 0 0 1 0 20M2 12h20" />
            </svg>
            <p className="text-sm text-[#858189]" style={{ fontFamily: "'Inter', sans-serif" }}>No KOL trades detected yet.</p>
            <p className="text-xs text-[#656169] mt-1" style={{ fontFamily: "'Inter', sans-serif" }}>The agent is monitoring whale wallets.</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {kols.map((k) => {
              const isExpanded = expandedId === k.id;
              const isLong = k.direction === "long";

              return (
                <div key={k.id}>
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : k.id)}
                    className={`w-full text-left bg-[#28272b] border p-3.5 transition-all group ${
                      isExpanded
                        ? "border-[#656169] bg-[#2e2d32] rounded-t-xl rounded-b-none"
                        : "border-[#3c3a41] rounded-xl hover:border-[#656169] hover:bg-[#2e2d32]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="text-sm font-medium text-white group-hover:text-white transition-colors" style={{ fontFamily: "'Inter', sans-serif" }}>
                          {k.kol_name}
                        </span>
                        <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded ${
                          isLong ? "bg-[#84f593]/10 text-[#84f593]" : "bg-[#f2685f]/10 text-[#f2685f]"
                        }`}>
                          {isLong ? "\u25B2" : "\u25BC"} {k.direction.toUpperCase()}
                        </span>
                        <span className="text-sm font-semibold" style={{ color: getAssetColor(k.asset), fontFamily: "'Sora', sans-serif" }}>
                          {k.asset}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0">
                        <span className="text-sm tabular-nums text-[#b8b5bb] font-medium" style={{ fontFamily: "'Inter', sans-serif" }}>
                          {formatUsd(k.trade_size_usd)}
                        </span>
                        <span className="text-[11px] text-[#656169] tabular-nums w-16 text-right" style={{ fontFamily: "'Inter', sans-serif" }}>
                          {timeAgo(k.detected_at)}
                        </span>
                        <svg
                          className={`w-3.5 h-3.5 text-[#656169] transition-transform ${isExpanded ? "rotate-180" : ""}`}
                          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                        >
                          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </div>
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="bg-[#2e2d32] border border-t-0 border-[#656169] rounded-b-xl p-4">
                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-[#656169] mb-0.5" style={{ fontFamily: "'Sora', sans-serif" }}>Wallet</div>
                          <div className="text-xs font-mono text-[#b8b5bb]">
                            {k.wallet_address.slice(0, 6)}...{k.wallet_address.slice(-4)}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-[#656169] mb-0.5" style={{ fontFamily: "'Sora', sans-serif" }}>Direction</div>
                          <div className={`text-sm font-semibold ${isLong ? "text-[#84f593]" : "text-[#f2685f]"}`}>
                            {k.direction.toUpperCase()}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-[#656169] mb-0.5" style={{ fontFamily: "'Sora', sans-serif" }}>Asset</div>
                          <div className="text-sm font-semibold" style={{ color: getAssetColor(k.asset) }}>{k.asset}</div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-[#656169] mb-0.5" style={{ fontFamily: "'Sora', sans-serif" }}>Size</div>
                          <div className="text-sm font-medium text-white tabular-nums">{formatUsd(k.trade_size_usd)}</div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-[#656169] mb-0.5" style={{ fontFamily: "'Sora', sans-serif" }}>Timestamp</div>
                          <div className="text-xs text-[#b8b5bb]" style={{ fontFamily: "'Inter', sans-serif" }}>
                            {new Date(k.detected_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                          </div>
                        </div>
                      </div>
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
