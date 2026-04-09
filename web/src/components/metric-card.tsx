interface MetricCardProps {
  label: string;
  value: string;
  delta?: string;
  deltaColor?: string;
}

export default function MetricCard({
  label,
  value,
  delta,
  deltaColor,
}: MetricCardProps) {
  return (
    <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-4 transition-all hover:border-[#656169] hover:bg-[#2e2d32]">
      <div className="text-[11px] font-medium uppercase tracking-wider text-[#858189] mb-1.5" style={{ fontFamily: "'Sora', sans-serif" }}>
        {label}
      </div>
      <div className="text-xl font-semibold text-white tabular-nums" style={{ fontFamily: "'Sora', sans-serif" }}>{value}</div>
      {delta && (
        <div className={`text-xs mt-1 ${deltaColor ?? "text-[#858189]"}`} style={{ fontFamily: "'Inter', sans-serif" }}>
          {delta}
        </div>
      )}
    </div>
  );
}
