import type { Signal } from "@/lib/types";

export default function SignalCard({ signal }: { signal: Signal }) {
  const positive = signal.price_change_pct >= 0;
  const color = positive ? "text-sf-up" : "text-sf-down";
  const sign = positive ? "+" : "";
  const ago = Math.round(
    (Date.now() - new Date(signal.detected_at).getTime()) / 60_000
  );

  return (
    <div className="bg-sf-card border border-sf-border rounded-lg p-3 transition-colors hover:border-sf-border-bold group">
      <div className="font-medium text-sm leading-snug line-clamp-2 text-sf-text-2 group-hover:text-sf-text transition-colors">
        {signal.market_question}
      </div>
      <div className="flex items-center gap-3 text-xs text-sf-muted mt-1.5">
        <span className="tabular-nums">{signal.current_price.toFixed(2)}</span>
        <span className={`font-semibold tabular-nums ${color}`}>
          {sign}{(signal.price_change_pct * 100).toFixed(1)}%
        </span>
        <span>{ago}m ago</span>
        {signal.category && (
          <span className="px-1.5 py-0.5 rounded bg-sf-card-alt text-sf-subtle text-[10px] uppercase tracking-wide">
            {signal.category}
          </span>
        )}
      </div>
    </div>
  );
}
