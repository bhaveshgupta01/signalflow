"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { COLORS, getAssetColor } from "@/lib/colors";

interface Slice {
  name: string;
  value: number;
}

export default function AllocationPie({ data }: { data: Slice[] }) {
  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={100}
          paddingAngle={2}
          dataKey="value"
          stroke="none"
        >
          {data.map((entry) => (
            <Cell
              key={entry.name}
              fill={entry.name === "Cash" ? COLORS.subtle : getAssetColor(entry.name)}
              opacity={entry.name === "Cash" ? 0.4 : 0.8}
            />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: COLORS.card,
            border: `1px solid ${COLORS.borderBold}`,
            borderRadius: 8,
            color: COLORS.text,
            fontSize: 12,
          }}
          formatter={(value) => {
            const v = Number(value);
            return [`$${v.toFixed(2)} (${((v / total) * 100).toFixed(1)}%)`, ""];
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: 11 }}
          formatter={(value) => <span style={{ color: COLORS.text2 }}>{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
