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
    <div className="bg-sf-card border border-sf-border rounded-lg p-4 transition-colors hover:border-sf-border-bold">
      <div className="text-[11px] font-medium uppercase tracking-wider text-sf-muted mb-1.5">
        {label}
      </div>
      <div className="text-xl font-semibold text-sf-text tabular-nums">{value}</div>
      {delta && (
        <div className={`text-xs mt-1 ${deltaColor ?? "text-sf-muted"}`}>
          {delta}
        </div>
      )}
    </div>
  );
}
