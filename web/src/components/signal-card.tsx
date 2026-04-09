import type { Signal } from "@/lib/types";

export default function SignalCard({ signal }: { signal: Signal }) {
  const positive = signal.price_change_pct >= 0;
  const color = positive ? "text-[#84f593]" : "text-[#f2685f]";
  const sign = positive ? "+" : "";
  const ago = Math.round(
    (Date.now() - new Date(signal.detected_at).getTime()) / 60_000
  );

  return (
    <div className="bg-[#28272b] border border-[#3c3a41] rounded-xl p-3 transition-all hover:border-[#656169] hover:bg-[#2e2d32] group">
      <div className="font-medium text-sm leading-snug line-clamp-2 text-[#b8b5bb] group-hover:text-white transition-colors" style={{ fontFamily: "'Inter', sans-serif" }}>
        {signal.market_question}
      </div>
      <div className="flex items-center gap-3 text-xs text-[#858189] mt-1.5" style={{ fontFamily: "'Inter', sans-serif" }}>
        <span className="tabular-nums">{signal.current_price.toFixed(2)}</span>
        <span className={`font-semibold tabular-nums ${color}`}>
          {sign}{(signal.price_change_pct * 100).toFixed(1)}%
        </span>
        <span>{ago}m ago</span>
        {signal.category && (
          <span className="px-2 py-0.5 rounded-full bg-[#1e1d21] text-[#858189] text-[10px] uppercase tracking-wide border border-[#3c3a41]">
            {signal.category}
          </span>
        )}
      </div>
    </div>
  );
}
