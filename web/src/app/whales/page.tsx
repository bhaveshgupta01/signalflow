"use client";

import { useEffect, useState, useMemo } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import MetricCard from "@/components/metric-card";
import { getAllKolSignals, getRecentSignals } from "@/lib/queries";
import { COLORS, getAssetColor } from "@/lib/colors";
import type { KolSignal, Signal } from "@/lib/types";

export default function WhalesPage() {
  const [kols, setKols] = useState<KolSignal[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);

  async function load() {
    const [k, s] = await Promise.all([
      getAllKolSignals(200),
      getRecentSignals(24 * 60),
    ]);
    setKols(k);
    setSignals(s);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);

  const uniqueKols = new Set(kols.map((k) => k.kol_name));
  const totalVolume = kols.reduce((s, k) => s + k.trade_size_usd, 0);
  const assets = [...new Set(kols.map((k) => k.asset))];

  // Volume by asset
  const volumeByAsset: Record<string, number> = {};
  for (const k of kols) {
    volumeByAsset[k.asset] = (volumeByAsset[k.asset] ?? 0) + k.trade_size_usd;
  }
  const sortedAssets = Object.entries(volumeByAsset).sort((a, b) => b[1] - a[1]);

  // Most active KOL
  const kolCounts: Record<string, number> = {};
  for (const k of kols) kolCounts[k.kol_name] = (kolCounts[k.kol_name] ?? 0) + 1;
  const topKol = Object.entries(kolCounts).sort((a, b) => b[1] - a[1])[0];

  // Most active asset
  const topAsset = sortedAssets[0];

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

  // Signal correlation: match KOL trades to Polymarket signals
  const correlations = useMemo(() => {
    return kols.slice(0, 20).map((k) => {
      const matchingSignal = signals.find(
        (s) =>
          s.market_question.toLowerCase().includes(k.asset.toLowerCase()) ||
          s.category.toLowerCase().includes(k.asset.toLowerCase())
      );
      const hasMatch = !!matchingSignal;
      let aligned = "N/A";
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
        polymarketMatch: hasMatch ? "Yes" : "No",
        aligned,
      };
    });
  }, [kols, signals]);

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-[1200px]">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-sf-text">Whale Intelligence</h1>
        <p className="text-sm text-sf-muted mt-0.5">
          KOL wallet tracking and smart-money alignment. Aligned signals get +15% conviction boost.
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard label="KOL Trades" value={String(kols.length)} delta="detected" />
        <MetricCard label="Unique KOLs" value={String(uniqueKols.size)} delta="wallets tracked" />
        <MetricCard
          label="Total Volume"
          value={`$${totalVolume.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
          delta={`across ${assets.length} assets`}
        />
        <MetricCard
          label="Most Active"
          value={topAsset?.[0] ?? "—"}
          delta={topAsset ? `$${topAsset[1].toLocaleString(undefined, { maximumFractionDigits: 0 })}` : ""}
        />
      </div>

      {/* Charts Row - Volume + Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Volume by Asset */}
        <section className="bg-sf-card border border-sf-border rounded-lg">
          <div className="p-4 border-b border-sf-border">
            <h2 className="text-sm font-semibold text-sf-text">Volume by Asset</h2>
            <p className="text-xs text-sf-muted mt-0.5">Total KOL trading volume per asset</p>
          </div>
          <div className="p-4">
            {sortedAssets.length > 0 ? (
              <div className="space-y-3">
                {sortedAssets.slice(0, 10).map(([asset, vol]) => {
                  const pct = totalVolume > 0 ? (vol / totalVolume) * 100 : 0;
                  return (
                    <div key={asset} className="flex items-center gap-3">
                      <span className="text-xs font-semibold w-14 text-right" style={{ color: getAssetColor(asset) }}>
                        {asset}
                      </span>
                      <div className="flex-1 bg-sf-bg rounded-full h-2 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-300"
                          style={{ width: `${Math.max(pct, 2)}%`, background: getAssetColor(asset), opacity: 0.7 }}
                        />
                      </div>
                      <span className="text-xs text-sf-muted w-24 text-right tabular-nums">
                        ${vol.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="py-8 text-center"><p className="text-xs text-sf-muted">No KOL volume data yet.</p></div>
            )}
          </div>
        </section>

        {/* Activity Timeline */}
        <section className="bg-sf-card border border-sf-border rounded-lg">
          <div className="p-4 border-b border-sf-border">
            <h2 className="text-sm font-semibold text-sf-text">Activity Timeline</h2>
            <p className="text-xs text-sf-muted mt-0.5">KOL trades over time by size</p>
          </div>
          <div className="p-4">
            {kols.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <ScatterChart>
                  <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    type="number"
                    domain={["auto", "auto"]}
                    tickFormatter={(v) => new Date(v).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    tick={{ fill: COLORS.muted, fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    dataKey="size"
                    name="Size ($)"
                    tick={{ fill: COLORS.muted, fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{ background: COLORS.card, border: `1px solid ${COLORS.borderBold}`, borderRadius: 8, color: COLORS.text, fontSize: 12 }}
                    labelFormatter={(v) => new Date(Number(v)).toLocaleString()}
                  />
                  <Scatter name="Long" data={longTrades} fill={COLORS.up} opacity={0.7} />
                  <Scatter name="Short" data={shortTrades} fill={COLORS.down} opacity={0.7} />
                </ScatterChart>
              </ResponsiveContainer>
            ) : (
              <div className="py-12 text-center"><p className="text-xs text-sf-muted">No timeline data yet.</p></div>
            )}
          </div>
        </section>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-sf-card border border-sf-border rounded-lg p-4">
          <div className="text-[11px] font-medium uppercase tracking-wider text-sf-muted mb-1">Most Active KOL</div>
          <div className="text-sm font-medium text-sf-text">{topKol ? topKol[0] : "—"}</div>
          {topKol && <div className="text-xs text-sf-muted">{topKol[1]} trades</div>}
        </div>
        <div className="bg-sf-card border border-sf-border rounded-lg p-4">
          <div className="text-[11px] font-medium uppercase tracking-wider text-sf-muted mb-1">Avg Trade Size</div>
          <div className="text-sm font-medium text-sf-text tabular-nums">
            ${kols.length > 0 ? (totalVolume / kols.length).toLocaleString(undefined, { maximumFractionDigits: 0 }) : "0"}
          </div>
        </div>
        <div className="bg-sf-card border border-sf-border rounded-lg p-4">
          <div className="text-[11px] font-medium uppercase tracking-wider text-sf-muted mb-1">Conviction Boost</div>
          <div className="text-sm font-medium text-sf-brand">+15%</div>
          <div className="text-xs text-sf-muted">when KOL aligns</div>
        </div>
        <div className="bg-sf-card border border-sf-border rounded-lg p-4">
          <div className="text-[11px] font-medium uppercase tracking-wider text-sf-muted mb-1">Agent Signals</div>
          <div className="text-sm font-medium text-sf-text">{signals.length}</div>
          <div className="text-xs text-sf-muted">last 24h</div>
        </div>
      </div>

      {/* Signal Correlation Table */}
      {correlations.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">
            Signal Correlation
          </h2>
          <p className="text-xs text-sf-subtle mb-3">
            When a KOL trade aligns with a Polymarket signal direction, the agent boosts conviction by 15%.
          </p>
          <div className="bg-sf-card border border-sf-border rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-sf-border bg-sf-surface/50">
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">KOL</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Asset</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Direction</th>
                    <th className="text-center px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Polymarket Match</th>
                    <th className="text-center px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Aligned</th>
                  </tr>
                </thead>
                <tbody>
                  {correlations.map((c) => (
                    <tr key={c.id} className="border-b border-sf-border/50 hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-2.5 font-medium text-sf-text text-sm truncate max-w-[150px]">{c.kol}</td>
                      <td className="px-4 py-2.5 font-medium text-sm" style={{ color: getAssetColor(c.asset) }}>{c.asset}</td>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                          c.direction === "long" ? "bg-sf-up/10 text-sf-up" : "bg-sf-down/10 text-sf-down"
                        }`}>
                          {c.direction.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <span className={`text-xs font-medium ${c.polymarketMatch === "Yes" ? "text-sf-up" : "text-sf-muted"}`}>
                          {c.polymarketMatch}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                          c.aligned === "Yes" ? "bg-sf-up/10 text-sf-up"
                            : c.aligned === "No" ? "bg-sf-down/10 text-sf-down"
                            : "text-sf-subtle"
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
        </section>
      )}

      {/* Whale Activity Table */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">
          Whale Activity Feed
        </h2>
        {kols.length === 0 ? (
          <div className="bg-sf-card border border-sf-border rounded-lg p-12 text-center">
            <svg className="w-8 h-8 text-sf-subtle mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" /><path d="M12 2a14.5 14.5 0 0 0 0 20M12 2a14.5 14.5 0 0 1 0 20M2 12h20" />
            </svg>
            <p className="text-sm text-sf-muted">No KOL trades detected yet.</p>
            <p className="text-xs text-sf-subtle mt-1">The agent is monitoring whale wallets.</p>
          </div>
        ) : (
          <div className="bg-sf-card border border-sf-border rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-sf-border bg-sf-surface/50">
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">KOL</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Dir</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Asset</th>
                    <th className="text-right px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Size</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Wallet</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-sf-muted">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {kols.slice(0, 30).map((k) => (
                    <tr key={k.id} className="border-b border-sf-border/50 hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-2.5 font-medium text-sf-text text-sm truncate max-w-[150px]">{k.kol_name}</td>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                          k.direction === "long" ? "bg-sf-up/10 text-sf-up" : "bg-sf-down/10 text-sf-down"
                        }`}>
                          {k.direction.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-medium text-sm" style={{ color: getAssetColor(k.asset) }}>{k.asset}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-sf-text-2">
                        ${k.trade_size_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </td>
                      <td className="px-4 py-2.5 text-[10px] text-sf-subtle font-mono">
                        {k.wallet_address.slice(0, 6)}...{k.wallet_address.slice(-4)}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-sf-muted tabular-nums">
                        {new Date(k.detected_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
