"use client";

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import { COLORS } from "@/lib/colors";
import type { Position, Analysis } from "@/lib/types";

interface Props {
  positions: Position[];
  analyses?: Analysis[];
}

export default function PnlScatter({ positions, analyses }: Props) {
  const closed = positions.filter((p) => p.status !== "open");

  // Build analysis lookup for conviction scores
  const analysisById = new Map((analyses ?? []).map((a) => [a.id, a]));

  const longs = closed
    .filter((p) => p.direction === "long")
    .map((p) => {
      const a = analysisById.get(p.analysis_id);
      return {
        conviction: a ? a.conviction_score * 100 : 50,
        pnl: p.pnl,
        asset: p.asset,
      };
    });
  const shorts = closed
    .filter((p) => p.direction === "short")
    .map((p) => {
      const a = analysisById.get(p.analysis_id);
      return {
        conviction: a ? a.conviction_score * 100 : 50,
        pnl: p.pnl,
        asset: p.asset,
      };
    });

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart>
        <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" />
        <XAxis
          dataKey="conviction"
          name="Conviction"
          unit="%"
          tick={{ fill: COLORS.muted, fontSize: 11 }}
          axisLine={false}
          domain={[0, 100]}
        />
        <YAxis
          dataKey="pnl"
          name="PnL ($)"
          tick={{ fill: COLORS.muted, fontSize: 11 }}
          axisLine={false}
        />
        <Tooltip
          contentStyle={{
            background: COLORS.card,
            border: `1px solid ${COLORS.borderBold}`,
            borderRadius: 12,
            color: COLORS.text,
            fontSize: 12,
          }}
        />
        <ReferenceLine y={0} stroke={COLORS.subtle} strokeDasharray="3 3" />
        <Scatter name="Longs" data={longs} fill={COLORS.up} opacity={0.8} />
        <Scatter name="Shorts" data={shorts} fill={COLORS.down} opacity={0.8} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
