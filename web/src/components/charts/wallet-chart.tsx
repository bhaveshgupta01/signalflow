"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { COLORS } from "@/lib/colors";
import type { WalletSnapshot } from "@/lib/types";

export default function WalletChart({ data }: { data: WalletSnapshot[] }) {
  const sorted = [...data].reverse();
  const chartData = sorted.map((s) => ({
    time: new Date(s.timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
    balance: Number(s.balance.toFixed(2)),
    pnl: Number(s.total_pnl.toFixed(2)),
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <AreaChart data={chartData}>
        <defs>
          <linearGradient id="balGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={COLORS.brand} stopOpacity={0.15} />
            <stop offset="100%" stopColor={COLORS.brand} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={COLORS.up} stopOpacity={0.1} />
            <stop offset="100%" stopColor={COLORS.up} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="time"
          tick={{ fill: COLORS.muted, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: COLORS.muted, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          domain={["auto", "auto"]}
          width={50}
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
        <Area
          type="monotone"
          dataKey="balance"
          stroke={COLORS.brand}
          strokeWidth={2}
          fill="url(#balGrad)"
          dot={false}
          name="Balance ($)"
        />
        <Area
          type="monotone"
          dataKey="pnl"
          stroke={COLORS.up}
          strokeWidth={1.5}
          fill="url(#pnlGrad)"
          dot={false}
          name="PnL ($)"
          strokeDasharray="4 4"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
