import Link from "next/link";

/* ── Helpers ──────────────────────────────────────────── */

function SectionHeader({ tag, title, desc }: { tag: string; title: string; desc: string }) {
  return (
    <div className="max-w-3xl">
      <div className="text-[11px] font-semibold uppercase tracking-widest text-[#bfa1f5] mb-2" style={{ fontFamily: "'Sora', sans-serif" }}>{tag}</div>
      <h2 className="text-2xl sm:text-3xl font-bold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>{title}</h2>
      <p className="text-sm text-[#b8b5bb] leading-relaxed mt-2" style={{ fontFamily: "'Inter', sans-serif" }}>{desc}</p>
    </div>
  );
}

function ToolBadge({ name }: { name: string }) {
  return (
    <code className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#8239ef]/10 text-[#bfa1f5] border border-[#8239ef]/20">
      {name}
    </code>
  );
}

function PhaseCard({
  step,
  title,
  color,
  badge,
  children,
}: {
  step: string;
  title: string;
  color: string;
  badge?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="boba-card p-5 sm:p-6">
      <div className="flex items-center gap-3 mb-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-xs font-bold flex-shrink-0"
          style={{ background: `${color}20`, color, fontFamily: "'Sora', sans-serif" }}
        >
          {step}
        </div>
        <h3 className="text-lg font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>{title}</h3>
        {badge && (
          <span
            className="text-[10px] font-semibold px-2.5 py-0.5 rounded-full ml-auto"
            style={{ background: `${color}20`, color, fontFamily: "'Sora', sans-serif" }}
          >
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

/* ── Page ─────────────────────────────────────────────── */

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#141316]">
      {/* ── Announcement banner ──────────────────────── */}
      <div className="bg-[#8239ef]/15 border-b border-[#8239ef]/20">
        <div className="max-w-6xl mx-auto px-6 py-2 flex items-center justify-center gap-2">
          <span className="text-[12px] font-medium text-[#bfa1f5]" style={{ fontFamily: "'Sora', sans-serif" }}>
            Built with Boba Agents MCP &mdash; 85+ tools, 9 blockchains, one connection
          </span>
        </div>
      </div>

      {/* ── Nav bar ───────────────────────────────────── */}
      <nav className="sticky top-0 z-40 bg-[#141316]/80 backdrop-blur-lg border-b border-[#3c3a41]">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-[#8239ef]/20 flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#bfa1f5" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
            </div>
            <span className="text-sm font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>SignalFlow</span>
          </div>
          <div className="flex items-center gap-3">
            <a href="https://boba.xyz" target="_blank" rel="noopener noreferrer" className="text-[13px] text-[#858189] hover:text-[#b8b5bb] transition-colors" style={{ fontFamily: "'Sora', sans-serif" }}>
              boba.xyz
            </a>
            <a href="https://agents.boba.xyz" target="_blank" rel="noopener noreferrer" className="text-[13px] text-[#858189] hover:text-[#b8b5bb] transition-colors" style={{ fontFamily: "'Sora', sans-serif" }}>
              Docs
            </a>
            <Link
              href="/dashboard"
              className="text-[13px] font-semibold px-4 py-2 bg-[#bfa1f5] text-[#141316] rounded-full hover:bg-[#d4bef8] transition-colors"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              Open Dashboard
            </Link>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-20 space-y-28">

        {/* ══════════════════════════════════════════════════
            1. HERO SECTION
            ══════════════════════════════════════════════════ */}
        <section className="text-center max-w-3xl mx-auto">
          <div className="flex justify-center gap-2 mb-6 flex-wrap">
            <span className="boba-pill bg-[#8239ef]/15 text-[#bfa1f5]">
              Powered by Boba
            </span>
            <span className="boba-pill bg-[#F59E0B]/15 text-[#F59E0B]">
              Gemini 2.5 Flash
            </span>
            <span className="boba-pill bg-[#84f593]/15 text-[#84f593]">
              Event-Driven
            </span>
          </div>
          <h1 className="text-4xl sm:text-6xl font-bold tracking-tight leading-[1.1]" style={{ fontFamily: "'Sora', sans-serif" }}>
            <span className="bg-gradient-to-r from-[#8239ef] via-[#bfa1f5] to-[#8239ef] bg-clip-text text-transparent">
              SignalFlow
            </span>
          </h1>
          <p className="text-lg sm:text-xl text-[#b8b5bb] leading-relaxed mt-5 max-w-2xl mx-auto" style={{ fontFamily: "'Inter', sans-serif" }}>
            An autonomous AI trading agent that turns prediction market signals
            into perpetual futures trades on Hyperliquid &mdash; powered entirely by{" "}
            <span className="text-[#bfa1f5] font-semibold">Boba Agents MCP</span>.
          </p>
          <p className="text-sm text-[#858189] leading-relaxed mt-3 max-w-xl mx-auto" style={{ fontFamily: "'Inter', sans-serif" }}>
            Six async triggers scan Polymarket, whale wallets, funding rates, token launches, and cross-chain prices.
            When a signal fires, Gemini 2.5 Flash Lite analyzes it, a 5-layer risk engine gates it,
            and Boba executes it on Hyperliquid perps &mdash; all autonomously.
          </p>
          <div className="flex justify-center gap-3 mt-8 flex-wrap">
            <Link
              href="/dashboard"
              className="px-7 py-3 bg-[#bfa1f5] text-[#141316] text-sm font-semibold rounded-full hover:bg-[#d4bef8] transition-colors"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              View Dashboard
            </Link>
            <a
              href="https://agents.boba.xyz"
              target="_blank"
              rel="noopener noreferrer"
              className="px-7 py-3 bg-transparent border border-[#3c3a41] text-sm font-semibold rounded-full hover:border-[#656169] hover:bg-[hsla(264,4%,64%,0.08)] transition-colors text-[#b8b5bb]"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              Boba Agents
            </a>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            2. STATS BAR
            ══════════════════════════════════════════════════ */}
        <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { val: "85+", label: "Boba Tools" },
            { val: "6", label: "Async Triggers" },
            { val: "9", label: "Blockchains" },
            { val: "$100", label: "Paper Wallet" },
          ].map((s) => (
            <div key={s.label} className="text-center py-5 rounded-xl bg-[#1e1d21] border border-[#3c3a41]">
              <div className="text-3xl font-bold tabular-nums text-white" style={{ fontFamily: "'Sora', sans-serif" }}>{s.val}</div>
              <div className="text-[11px] text-[#858189] uppercase tracking-wider mt-1" style={{ fontFamily: "'Sora', sans-serif" }}>{s.label}</div>
            </div>
          ))}
        </section>

        {/* ══════════════════════════════════════════════════
            3. HOW IT WORKS - 5-Phase Pipeline
            ══════════════════════════════════════════════════ */}
        <section>
          <SectionHeader
            tag="How It Works"
            title="Complete 5-Phase Trade Lifecycle"
            desc="Every trade flows through a deterministic pipeline: scan, analyze, risk-gate, execute, manage. Six independent triggers feed signals into an asyncio event bus, and the agent processes them in order."
          />

          <div className="mt-10 space-y-5">

            {/* Phase 01 - SCAN */}
            <PhaseCard step="01" title="SCAN" color="#8239ef" badge="6 TRIGGERS">
              <p className="text-sm text-[#b8b5bb] leading-relaxed mb-4" style={{ fontFamily: "'Inter', sans-serif" }}>
                Six async triggers poll data sources in parallel. Each runs on its own timer, producing events that enter the central asyncio.Queue when thresholds are crossed.
              </p>
              <div className="space-y-3">
                {[
                  {
                    name: "Polymarket Scanner",
                    interval: "Every 40s",
                    tools: ["pm_search_markets", "pm_get_price_history"],
                    desc: "Searches across 8 market categories for prediction markets with 4%+ probability moves in the last hour. Detects sentiment shifts before they reach spot markets.",
                  },
                  {
                    name: "KOL Whale Tracker",
                    interval: "Every 50s",
                    tools: ["get_kol_swaps"],
                    desc: "Monitors smart money wallets for trades exceeding $300. Tracks 429 KOL wallets and flags directional consensus among top traders.",
                  },
                  {
                    name: "Funding Rate Monitor",
                    interval: "Every 75s",
                    tools: ["hl_get_predicted_funding"],
                    desc: "Detects Hyperliquid vs Binance funding rate divergence greater than 0.01%. Crowded positioning creates mean-reversion opportunities.",
                  },
                  {
                    name: "Token Discovery",
                    interval: "Every 100s",
                    tools: ["search_tokens", "get_brewing_tokens"],
                    desc: "Finds tokens with >50% 24-hour gains and >$100k volume. Monitors launchpad graduation events for early momentum plays.",
                  },
                  {
                    name: "Cross-Chain Arb",
                    interval: "Every 150s",
                    tools: ["get_token_price"],
                    desc: "Compares prices for the same token across 9 blockchains. Flags >0.3% price differences before arbitrageurs close the spread.",
                  },
                  {
                    name: "Portfolio Sync",
                    interval: "Every 240s",
                    tools: ["get_portfolio"],
                    desc: "Reconciles wallet state, updates equity curve, and recalculates available margin for new positions.",
                  },
                ].map((trigger) => (
                  <div key={trigger.name} className="bg-[#1e1d21] border border-[#3c3a41] rounded-lg p-3 sm:p-4">
                    <div className="flex items-center justify-between mb-1.5 flex-wrap gap-2">
                      <span className="text-sm font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>{trigger.name}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#8239ef]/10 text-[#bfa1f5] border border-[#8239ef]/20">
                        {trigger.interval}
                      </span>
                    </div>
                    <p className="text-xs text-[#b8b5bb] leading-relaxed mb-2" style={{ fontFamily: "'Inter', sans-serif" }}>{trigger.desc}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {trigger.tools.map((t) => <ToolBadge key={t} name={t} />)}
                    </div>
                  </div>
                ))}
              </div>
            </PhaseCard>

            {/* Phase 02 - ANALYZE */}
            <PhaseCard step="02" title="ANALYZE" color="#bfa1f5" badge="GEMINI 2.5 FLASH LITE">
              <p className="text-sm text-[#b8b5bb] leading-relaxed mb-4" style={{ fontFamily: "'Inter', sans-serif" }}>
                When a signal enters the event bus, Gemini 2.5 Flash Lite performs structured multi-step analysis using Boba tools as function calls.
                The AI has access to all 85+ tools but follows a disciplined evaluation framework.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                <div className="bg-[#1e1d21] border border-[#3c3a41] rounded-lg p-3">
                  <h4 className="text-xs font-semibold text-[#858189] uppercase tracking-wider mb-2" style={{ fontFamily: "'Sora', sans-serif" }}>Data Gathering</h4>
                  <ul className="space-y-1.5 text-xs text-[#b8b5bb]" style={{ fontFamily: "'Inter', sans-serif" }}>
                    <li className="flex items-start gap-2">
                      <span className="text-[#bfa1f5] mt-0.5">1.</span>
                      Fetches holder data via <ToolBadge name="pm_get_top_holders" />
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-[#bfa1f5] mt-0.5">2.</span>
                      Reads community sentiment via <ToolBadge name="pm_get_comments" />
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-[#bfa1f5] mt-0.5">3.</span>
                      Checks spot structure via <ToolBadge name="hl_get_asset" /> <ToolBadge name="hl_get_markets" /> <ToolBadge name="hl_get_history" />
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-[#bfa1f5] mt-0.5">4.</span>
                      Evaluates derivatives positioning via <ToolBadge name="hl_get_orderbook" /> <ToolBadge name="hl_get_predicted_funding" />
                    </li>
                  </ul>
                </div>
                <div className="bg-[#1e1d21] border border-[#3c3a41] rounded-lg p-3">
                  <h4 className="text-xs font-semibold text-[#858189] uppercase tracking-wider mb-2" style={{ fontFamily: "'Sora', sans-serif" }}>Hypothesis Generation</h4>
                  <ul className="space-y-1.5 text-xs text-[#b8b5bb]" style={{ fontFamily: "'Inter', sans-serif" }}>
                    <li><span className="text-white font-medium">Thesis:</span> directional view with reasoning</li>
                    <li><span className="text-white font-medium">Edge Type:</span> flow / mean_reversion / narrative / sentiment</li>
                    <li><span className="text-white font-medium">Edge Depth:</span> deep (structural) or shallow (fleeting)</li>
                    <li><span className="text-white font-medium">Invalidation:</span> specific condition that kills the trade</li>
                  </ul>
                </div>
              </div>
              <div className="bg-[#1e1d21] border border-[#3c3a41] rounded-lg p-3">
                <h4 className="text-xs font-semibold text-[#858189] uppercase tracking-wider mb-2" style={{ fontFamily: "'Sora', sans-serif" }}>Output Schema</h4>
                <div className="font-mono text-xs text-[#b8b5bb] space-y-0.5 leading-relaxed">
                  <div>{"{"} <span className="text-[#84f593]">conviction</span>: <span className="text-white">0.78</span>, <span className="text-[#84f593]">direction</span>: <span className="text-white">&quot;long&quot;</span>, <span className="text-[#84f593]">asset</span>: <span className="text-white">&quot;BTC&quot;</span>,</div>
                  <div>&nbsp;&nbsp;<span className="text-[#84f593]">size_pct</span>: <span className="text-white">25</span>, <span className="text-[#84f593]">leverage</span>: <span className="text-white">5</span>, <span className="text-[#84f593]">hold_hours</span>: <span className="text-white">4</span>,</div>
                  <div>&nbsp;&nbsp;<span className="text-[#84f593]">edge_type</span>: <span className="text-white">&quot;sentiment&quot;</span>, <span className="text-[#84f593]">reasoning</span>: <span className="text-white">&quot;...&quot;</span> {"}"}</div>
                </div>
                <p className="text-xs text-[#858189] mt-2" style={{ fontFamily: "'Inter', sans-serif" }}>
                  KOL alignment check: if a whale traded the same direction in the last 60 minutes, conviction gets a +15% boost.
                </p>
              </div>
            </PhaseCard>

            {/* Phase 03 - RISK GATE */}
            <PhaseCard step="03" title="RISK GATE" color="#F59E0B" badge="NO LLM">
              <p className="text-sm text-[#b8b5bb] leading-relaxed mb-4" style={{ fontFamily: "'Inter', sans-serif" }}>
                A 5-layer deterministic risk engine with zero LLM involvement. No amount of AI confidence can override these checks.
                Every trade must pass all 5 layers or it is rejected.
              </p>
              <div className="space-y-3">
                {[
                  {
                    layer: "1",
                    name: "Drawdown Circuit Breaker",
                    color: "#f2685f",
                    details: [
                      { label: "< 15% drawdown", value: "Normal operation", valueColor: "#84f593" },
                      { label: "15 - 30% drawdown", value: "Halve all position sizes", valueColor: "#F59E0B" },
                      { label: "> 30% drawdown", value: "Halt trading for 4 hours", valueColor: "#f2685f" },
                    ],
                  },
                  {
                    layer: "2",
                    name: "Position Limits",
                    color: "#F59E0B",
                    details: [
                      { label: "Max positions", value: "8 concurrent", valueColor: "#b8b5bb" },
                      { label: "Cash reserve", value: "10% always held back", valueColor: "#b8b5bb" },
                      { label: "Max per trade", value: "30% of portfolio", valueColor: "#b8b5bb" },
                      { label: "Trade cooldown", value: "3 minutes between trades", valueColor: "#b8b5bb" },
                      { label: "Flip cooldown", value: "10 minutes same-asset reversal", valueColor: "#b8b5bb" },
                    ],
                  },
                  {
                    layer: "3",
                    name: "Orderbook Liquidity",
                    color: "#bfa1f5",
                    details: [
                      { label: "Depth check", value: "Requires $500 within 1% of mid via hl_get_orderbook", valueColor: "#b8b5bb" },
                      { label: "Slippage limit", value: "Rejects if estimated slippage > 5%", valueColor: "#b8b5bb" },
                    ],
                  },
                  {
                    layer: "4",
                    name: "ATR Dynamic Stops",
                    color: "#84f593",
                    details: [
                      { label: "ATR source", value: "14-period ATR from 1-hour candles", valueColor: "#b8b5bb" },
                      { label: "Stop-loss", value: "min(ATR x 1.5, 5%)", valueColor: "#f2685f" },
                      { label: "Take-profit", value: "min(ATR x 3, 12%)", valueColor: "#84f593" },
                      { label: "Risk:Reward", value: "Minimum 2:1 enforced", valueColor: "#b8b5bb" },
                    ],
                  },
                  {
                    layer: "5",
                    name: "Fill Confirmation",
                    color: "#bfa1f5",
                    details: [
                      { label: "Post-execution", value: "hl_get_fills confirms actual entry price", valueColor: "#b8b5bb" },
                      { label: "Slippage tracking", value: "Measures expected vs actual fill", valueColor: "#b8b5bb" },
                      { label: "SL/TP adjustment", value: "Recalculates from actual entry, not intended", valueColor: "#b8b5bb" },
                    ],
                  },
                ].map((layer) => (
                  <div key={layer.layer} className="bg-[#1e1d21] border border-[#3c3a41] rounded-lg p-3 sm:p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className="w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-bold flex-shrink-0"
                        style={{ background: `${layer.color}20`, color: layer.color, fontFamily: "'Sora', sans-serif" }}
                      >
                        {layer.layer}
                      </span>
                      <span className="text-sm font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>{layer.name}</span>
                    </div>
                    <div className="space-y-1">
                      {layer.details.map((d, i) => (
                        <div key={i} className="flex items-start gap-2 text-xs">
                          <span className="text-[#858189] min-w-[130px] flex-shrink-0" style={{ fontFamily: "'Inter', sans-serif" }}>{d.label}</span>
                          <span style={{ color: d.valueColor, fontFamily: "'Inter', sans-serif" }}>{d.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </PhaseCard>

            {/* Phase 04 - EXECUTE */}
            <PhaseCard step="04" title="EXECUTE" color="#84f593" badge="HYPERLIQUID">
              <p className="text-sm text-[#b8b5bb] leading-relaxed mb-4" style={{ fontFamily: "'Inter', sans-serif" }}>
                Direct execution on Hyperliquid perpetual futures via Boba MCP. Every trade follows a strict 5-step sequence.
              </p>
              <div className="bg-[#1e1d21] border border-[#3c3a41] rounded-lg p-4">
                <div className="font-mono text-xs space-y-2.5 leading-relaxed">
                  {[
                    { step: "1", tool: "hl_update_leverage", desc: "Set conviction-based leverage (2-7x)" },
                    { step: "2", tool: "hl_place_order", desc: 'Market entry (type="market")' },
                    { step: "3", tool: "hl_get_fills", desc: "Confirm fill price, measure slippage" },
                    { step: "4", tool: "hl_place_order", desc: 'Stop-loss order (type="stop")' },
                    { step: "5", tool: "hl_place_order", desc: 'Take-profit order (type="take_profit")' },
                  ].map((s) => (
                    <div key={s.step} className="flex items-start gap-3">
                      <span className="text-[#84f593] font-bold w-4 flex-shrink-0">{s.step}.</span>
                      <span className="text-[#bfa1f5]">{s.tool}</span>
                      <span className="text-[#858189]">&rarr;</span>
                      <span className="text-[#b8b5bb]">{s.desc}</span>
                    </div>
                  ))}
                </div>
              </div>
            </PhaseCard>

            {/* Phase 05 - MANAGE */}
            <PhaseCard step="05" title="MANAGE" color="#f2685f" badge="CONTINUOUS">
              <p className="text-sm text-[#b8b5bb] leading-relaxed mb-4" style={{ fontFamily: "'Inter', sans-serif" }}>
                Open positions are monitored every cycle. Five management rules run in priority order.
              </p>
              <div className="space-y-2">
                {[
                  {
                    rule: "Hard SL/TP",
                    desc: "Instant close via hl_close_position if price hits stop-loss or take-profit levels",
                    color: "#f2685f",
                  },
                  {
                    rule: "Trailing Stop",
                    desc: "When PnL exceeds +5%, stop-loss moves to break-even to lock in gains",
                    color: "#84f593",
                  },
                  {
                    rule: "Planned Hold",
                    desc: "At hold_hours, AI re-evaluates (checks trend, funding, whale activity) and decides: hold or close",
                    color: "#bfa1f5",
                  },
                  {
                    rule: "Smart Early Exit",
                    desc: "At 50% of hold time, if losing >2%, AI evaluates whether to cut losses early",
                    color: "#F59E0B",
                  },
                  {
                    rule: "Hard Age Limit",
                    desc: "Force-close after 8 hours regardless of PnL. No position runs overnight.",
                    color: "#f2685f",
                  },
                ].map((r) => (
                  <div key={r.rule} className="flex items-start gap-3 bg-[#1e1d21] border border-[#3c3a41] rounded-lg p-3">
                    <span
                      className="text-[10px] font-semibold px-2 py-0.5 rounded-full flex-shrink-0 mt-0.5"
                      style={{ background: `${r.color}20`, color: r.color, fontFamily: "'Sora', sans-serif" }}
                    >
                      {r.rule}
                    </span>
                    <span className="text-xs text-[#b8b5bb] leading-relaxed" style={{ fontFamily: "'Inter', sans-serif" }}>{r.desc}</span>
                  </div>
                ))}
              </div>
            </PhaseCard>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            4. AI-MANAGED LEVERAGE
            ══════════════════════════════════════════════════ */}
        <section>
          <SectionHeader
            tag="Leverage"
            title="AI-Managed Leverage"
            desc="Leverage is never static. It scales dynamically with the AI's conviction score, so higher-confidence trades get more exposure while low-confidence trades stay conservative."
          />
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { range: "< 0.4", maxLev: "2x", label: "Low Confidence", color: "#858189", desc: "Weak or ambiguous signal. Minimal exposure." },
              { range: "0.4 - 0.6", maxLev: "3x", label: "Moderate Edge", color: "#F59E0B", desc: "Directional lean with some supporting data." },
              { range: "0.6 - 0.8", maxLev: "5x", label: "Strong Edge", color: "#bfa1f5", desc: "Multiple signals align. Whale confirmation likely." },
              { range: "> 0.8", maxLev: "7x", label: "Exceptional", color: "#84f593", desc: "Rare. Multi-source convergence with deep edge." },
            ].map((tier) => (
              <div key={tier.range} className="boba-card p-4 text-center">
                <div className="text-[10px] font-semibold uppercase tracking-wider mb-2" style={{ color: tier.color, fontFamily: "'Sora', sans-serif" }}>
                  {tier.label}
                </div>
                <div className="text-3xl font-bold text-white mb-1" style={{ fontFamily: "'Sora', sans-serif" }}>
                  {tier.maxLev}
                </div>
                <div className="text-xs font-mono text-[#858189] mb-2">
                  conviction {tier.range}
                </div>
                <p className="text-[11px] text-[#b8b5bb] leading-relaxed" style={{ fontFamily: "'Inter', sans-serif" }}>
                  {tier.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            5. BOBA MCP ENGINE
            ══════════════════════════════════════════════════ */}
        <section>
          <SectionHeader
            tag="The Engine"
            title="Boba Agents MCP"
            desc="One MCP endpoint. 85+ tools. 9 blockchains. Boba handles authentication, rate limiting, chain routing, and data normalization. SignalFlow uses 19 tools across 5 categories."
          />

          <div className="mt-8 space-y-4">
            {/* Tool categories */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {[
                {
                  category: "Polymarket",
                  count: 4,
                  color: "#bfa1f5",
                  tools: ["pm_search_markets", "pm_get_price_history", "pm_get_top_holders", "pm_get_comments"],
                },
                {
                  category: "Hyperliquid",
                  count: 9,
                  color: "#84f593",
                  tools: ["hl_get_asset", "hl_get_markets", "hl_get_history", "hl_get_orderbook", "hl_get_predicted_funding", "hl_place_order", "hl_update_leverage", "hl_close_position", "hl_get_fills"],
                },
                {
                  category: "Token Discovery",
                  count: 4,
                  color: "#F59E0B",
                  tools: ["search_tokens", "get_brewing_tokens", "get_token_price", "audit_token"],
                },
                {
                  category: "KOL Intelligence",
                  count: 1,
                  color: "#f2685f",
                  tools: ["get_kol_swaps"],
                },
                {
                  category: "Portfolio",
                  count: 1,
                  color: "#858189",
                  tools: ["get_portfolio"],
                },
              ].map((cat) => (
                <div key={cat.category} className="boba-card p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>{cat.category}</span>
                    <span
                      className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                      style={{ background: `${cat.color}20`, color: cat.color, fontFamily: "'Sora', sans-serif" }}
                    >
                      {cat.count} tools
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {cat.tools.map((t) => <ToolBadge key={t} name={t} />)}
                  </div>
                </div>
              ))}
            </div>

            {/* Execution flow */}
            <div className="bg-[#1e1d21] border border-[#3c3a41] rounded-xl p-5 sm:p-6">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-[#858189] mb-4" style={{ fontFamily: "'Sora', sans-serif" }}>Complete Execution Flow</h4>
              <div className="font-mono text-xs text-[#b8b5bb] space-y-2 leading-relaxed">
                <div><span className="text-[#656169]">1.</span> Trigger fires &rarr; event enters <span className="text-white">asyncio.Queue</span></div>
                <div><span className="text-[#656169]">2.</span> Agent calls <span className="text-[#bfa1f5]">pm_search_markets</span> + <span className="text-[#bfa1f5]">pm_get_price_history</span> to validate signal</div>
                <div><span className="text-[#656169]">3.</span> Fetches holder data via <span className="text-[#bfa1f5]">pm_get_top_holders</span> + sentiment via <span className="text-[#bfa1f5]">pm_get_comments</span></div>
                <div><span className="text-[#656169]">4.</span> Checks spot via <span className="text-[#bfa1f5]">hl_get_asset</span> + <span className="text-[#bfa1f5]">hl_get_markets</span> + <span className="text-[#bfa1f5]">hl_get_history</span></div>
                <div><span className="text-[#656169]">5.</span> Evaluates derivatives via <span className="text-[#bfa1f5]">hl_get_orderbook</span> + <span className="text-[#bfa1f5]">hl_get_predicted_funding</span></div>
                <div><span className="text-[#656169]">6.</span> Checks whale alignment via <span className="text-[#bfa1f5]">get_kol_swaps</span> <span className="text-[#858189]">(+15% conviction if same direction in 60 min)</span></div>
                <div><span className="text-[#656169]">7.</span> Gemini returns: <span className="text-[#84f593]">{"{"} direction, conviction, asset, size, leverage, hold_time {"}"}</span></div>
                <div><span className="text-[#656169]">8.</span> Risk engine validates 5 layers <span className="text-[#858189]">(drawdown, limits, liquidity, ATR stops, fills)</span></div>
                <div><span className="text-[#656169]">9.</span> <span className="text-[#bfa1f5]">hl_update_leverage</span> &rarr; <span className="text-[#bfa1f5]">hl_place_order</span> (market) &rarr; <span className="text-[#bfa1f5]">hl_get_fills</span></div>
                <div><span className="text-[#656169]">10.</span> <span className="text-[#bfa1f5]">hl_place_order</span> (stop) + <span className="text-[#bfa1f5]">hl_place_order</span> (take_profit) placed from actual fill</div>
                <div><span className="text-[#656169]">11.</span> Position enters management loop &rarr; trailing stop, planned exit, hard age limit</div>
              </div>
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            6. SIGNAL INTERPRETATION
            ══════════════════════════════════════════════════ */}
        <section>
          <SectionHeader
            tag="Signal Logic"
            title="Signal Interpretation"
            desc="Prediction market probabilities are inherently about events, not prices. The AI must invert the signal to derive a directional trade. Here is how it reasons:"
          />

          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              {
                market: '"Will BTC dip below $60k?"',
                move: "Probability FALLS",
                interpretation: "Dip is LESS likely",
                direction: "BULLISH",
                color: "#84f593",
                icon: "\u2191",
              },
              {
                market: '"Will BTC dip below $60k?"',
                move: "Probability RISES",
                interpretation: "Dip is MORE likely",
                direction: "BEARISH",
                color: "#f2685f",
                icon: "\u2193",
              },
              {
                market: '"Will SOL reach $110?"',
                move: "Probability RISES",
                interpretation: "Target more likely to be hit",
                direction: "BULLISH",
                color: "#84f593",
                icon: "\u2191",
              },
              {
                market: '"Will SOL reach $110?"',
                move: "Probability FALLS",
                interpretation: "Target less likely",
                direction: "CROSS-REFERENCE",
                color: "#F59E0B",
                icon: "?",
              },
            ].map((s, i) => (
              <div key={i} className="boba-card p-4">
                <p className="text-xs font-mono text-[#bfa1f5] mb-2">{s.market}</p>
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-sm font-bold flex-shrink-0"
                    style={{ background: `${s.color}20`, color: s.color }}
                  >
                    {s.icon}
                  </span>
                  <div>
                    <div className="text-sm font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>{s.move}</div>
                    <div className="text-xs text-[#858189]" style={{ fontFamily: "'Inter', sans-serif" }}>{s.interpretation}</div>
                  </div>
                  <span
                    className="text-[10px] font-bold px-2.5 py-0.5 rounded-full ml-auto"
                    style={{ background: `${s.color}20`, color: s.color, fontFamily: "'Sora', sans-serif" }}
                  >
                    {s.direction}
                  </span>
                </div>
                {s.direction === "CROSS-REFERENCE" && (
                  <p className="text-[11px] text-[#858189] leading-relaxed mt-1" style={{ fontFamily: "'Inter', sans-serif" }}>
                    Not necessarily bearish. Must cross-reference with spot price action, funding rates, and whale positioning before committing.
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            7. TRADING STRATEGIES
            ══════════════════════════════════════════════════ */}
        <section>
          <SectionHeader
            tag="Strategies"
            title="5 Trading Strategies"
            desc="Five parallel strategies scan different data sources for trading opportunities. Each runs independently on its own trigger timer."
          />
          <div className="mt-8 space-y-3">
            {[
              {
                num: "01",
                name: "Prediction Market Signals",
                desc: "Scans Polymarket for crypto prediction markets with 4%+ probability moves in the last hour. Interprets the probability shift to derive a directional perps trade. Covers 8 market categories including price targets, regulatory events, and ETF approvals.",
                tools: ["pm_search_markets", "pm_get_price_history", "pm_get_top_holders", "pm_get_comments"],
                color: "#bfa1f5",
              },
              {
                num: "02",
                name: "KOL Whale Tracking",
                desc: "Monitors 429 smart-money wallets for trades exceeding $300. When a whale trades in the same direction as an existing signal within 60 minutes, the signal receives a +15% conviction boost. Pure whale signals (without other triggers) can also generate trades.",
                tools: ["get_kol_swaps"],
                color: "#f2685f",
              },
              {
                num: "03",
                name: "Funding Rate Arbitrage",
                desc: "Detects when Hyperliquid predicted funding diverges >0.01% from Binance rates. Crowded longs pay elevated funding, creating short opportunities. Crowded shorts create long opportunities. Trades the spread before convergence.",
                tools: ["hl_get_predicted_funding"],
                color: "#84f593",
              },
              {
                num: "04",
                name: "Token Discovery",
                desc: "Finds tokens with >50% 24-hour price gains and >$100k trading volume. Monitors launchpad graduation events via get_brewing_tokens for early momentum plays. Runs security audits before recommending any new token.",
                tools: ["search_tokens", "get_brewing_tokens", "audit_token"],
                color: "#F59E0B",
              },
              {
                num: "05",
                name: "Cross-Chain Arbitrage",
                desc: "Compares prices for the same token across 9 supported blockchains. Flags opportunities when price differences exceed 0.3%. Speed is critical as arbitrageurs typically close these spreads within minutes.",
                tools: ["get_token_price"],
                color: "#858189",
              },
            ].map((s) => (
              <div key={s.num} className="boba-card p-4 sm:p-5">
                <div className="flex items-center gap-3 mb-2">
                  <span
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
                    style={{ background: `${s.color}20`, color: s.color, fontFamily: "'Sora', sans-serif" }}
                  >
                    {s.num}
                  </span>
                  <h3 className="text-sm sm:text-base font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>{s.name}</h3>
                </div>
                <p className="text-xs text-[#b8b5bb] leading-relaxed mb-3 ml-11" style={{ fontFamily: "'Inter', sans-serif" }}>{s.desc}</p>
                <div className="flex flex-wrap gap-1.5 ml-11">
                  {s.tools.map((t) => <ToolBadge key={t} name={t} />)}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            8. RISK PARAMETERS TABLE
            ══════════════════════════════════════════════════ */}
        <section>
          <SectionHeader
            tag="Risk Management"
            title="Risk Parameters"
            desc="Every parameter is hard-coded and deterministic. The AI cannot override or relax any of these limits."
          />
          <div className="mt-8 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { val: "ATR x 1.5", sub: "max 5%", label: "Stop-Loss", color: "#f2685f" },
              { val: "ATR x 3", sub: "max 12%", label: "Take-Profit", color: "#84f593" },
              { val: "7x", sub: "conviction-based", label: "Max Leverage", color: "#bfa1f5" },
              { val: "8h", sub: "force-close", label: "Max Hold Time", color: "#F59E0B" },
              { val: "8", sub: "concurrent", label: "Max Positions", color: "#858189" },
              { val: "$1,000", sub: "total", label: "Max Exposure", color: "#b8b5bb" },
              { val: "30%", sub: "halt 4 hours", label: "Drawdown Halt", color: "#f2685f" },
              { val: "10%", sub: "always reserved", label: "Cash Reserve", color: "#84f593" },
            ].map((r) => (
              <div key={r.label} className="boba-card p-4 text-center">
                <div className="text-xl font-bold tabular-nums text-white" style={{ fontFamily: "'Sora', sans-serif" }}>{r.val}</div>
                <div className="text-[10px] mt-0.5" style={{ color: r.color, fontFamily: "'Inter', sans-serif" }}>{r.sub}</div>
                <div className="text-[10px] text-[#858189] uppercase tracking-wider mt-2" style={{ fontFamily: "'Sora', sans-serif" }}>{r.label}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            9. ARCHITECTURE
            ══════════════════════════════════════════════════ */}
        <section>
          <SectionHeader
            tag="Architecture"
            title="System Components"
            desc="Modular architecture with clear separation of concerns. Each component is independently testable and replaceable."
          />
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {[
              {
                title: "AI Brain",
                tag: "gemini",
                tagColor: "#bfa1f5",
                desc: "Gemini 2.5 Flash Lite with full function-calling access to 85+ Boba tools. Returns structured JSON with conviction scoring, edge classification, and invalidation conditions.",
              },
              {
                title: "Event Bus",
                tag: "asyncio",
                tagColor: "#84f593",
                desc: "asyncio.Queue connects 6 independent triggers to a single agent loop. Events are processed in order with backpressure. Each trigger runs on its own timer without blocking others.",
              },
              {
                title: "Risk Engine",
                tag: "5-layer",
                tagColor: "#F59E0B",
                desc: "Pure Python, zero LLM involvement. Enforces drawdown circuit breakers, position limits, orderbook liquidity checks, ATR-based dynamic stops, and fill confirmation.",
              },
              {
                title: "Database",
                tag: "sqlite",
                tagColor: "#858189",
                desc: "SQLite with WAL mode for concurrent reads from the dashboard and writes from the agent. Stores trades, signals, portfolio snapshots, and equity curve history.",
              },
              {
                title: "Dashboard",
                tag: "next.js",
                tagColor: "#bfa1f5",
                desc: "Next.js App Router with Recharts. 5 pages: Command Center, Portfolio, Scanner, Performance, and Whales. Auto-refresh with Boba-themed dark UI.",
              },
              {
                title: "Deployment",
                tag: "docker",
                tagColor: "#84f593",
                desc: "Python agent runs in Docker. Dashboard deploys to Vercel with git push. Single docker-compose.yml for the complete stack.",
              },
            ].map((a) => (
              <div key={a.title} className="boba-card p-4 sm:p-5">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-semibold text-white" style={{ fontFamily: "'Sora', sans-serif" }}>{a.title}</h4>
                  <span
                    className="text-[9px] font-mono px-2 py-0.5 rounded-full uppercase border"
                    style={{ background: `${a.tagColor}10`, color: a.tagColor, borderColor: `${a.tagColor}30` }}
                  >
                    {a.tag}
                  </span>
                </div>
                <p className="text-xs text-[#b8b5bb] leading-relaxed" style={{ fontFamily: "'Inter', sans-serif" }}>{a.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            10. TECH STACK
            ══════════════════════════════════════════════════ */}
        <section>
          <SectionHeader
            tag="Stack"
            title="Technology"
            desc="Purpose-built with a minimal, focused stack. Every dependency earns its place."
          />
          <div className="mt-8 grid grid-cols-2 sm:grid-cols-5 gap-2">
            {[
              { name: "Boba Agents MCP", role: "85+ tools, 9 chains", color: "#8239ef" },
              { name: "Gemini 2.5 Flash", role: "AI decision engine", color: "#bfa1f5" },
              { name: "Hyperliquid", role: "Perps execution", color: "#84f593" },
              { name: "Polymarket", role: "Signal source", color: "#F59E0B" },
              { name: "Next.js 16", role: "Dashboard", color: "#b8b5bb" },
              { name: "SQLite WAL", role: "Database", color: "#858189" },
              { name: "Recharts", role: "Visualizations", color: "#bfa1f5" },
              { name: "Pydantic v2", role: "Data models", color: "#84f593" },
              { name: "asyncio", role: "Concurrency", color: "#F59E0B" },
              { name: "Docker", role: "Deployment", color: "#858189" },
            ].map((t) => (
              <div key={t.name} className="boba-card px-3 py-3 text-center">
                <div className="text-sm font-semibold text-white mb-0.5" style={{ fontFamily: "'Sora', sans-serif" }}>{t.name}</div>
                <div className="text-[10px]" style={{ color: t.color, fontFamily: "'Inter', sans-serif" }}>{t.role}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            11. DATA FLOW DIAGRAM
            ══════════════════════════════════════════════════ */}
        <section>
          <SectionHeader
            tag="Data Flow"
            title="End-to-End Pipeline"
            desc="The complete data flow from triggers through execution to the dashboard."
          />
          <div className="mt-8 bg-[#1e1d21] border border-[#3c3a41] rounded-xl p-5 sm:p-6 overflow-x-auto">
            <div className="font-mono text-xs leading-loose min-w-[600px]">
              {/* Row 1: Triggers */}
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className="text-[#858189]">{"// 6 Triggers (parallel)"}</span>
              </div>
              <div className="flex items-center gap-2 flex-wrap mb-3">
                {["Polymarket 40s", "KOL 50s", "Funding 75s", "Tokens 100s", "X-Chain 150s", "Portfolio 240s"].map((t) => (
                  <span key={t} className="px-2 py-1 rounded-md bg-[#8239ef]/10 text-[#bfa1f5] border border-[#8239ef]/20 text-[10px]">
                    {t}
                  </span>
                ))}
              </div>

              {/* Arrow */}
              <div className="text-[#656169] mb-3 pl-4">&darr;&darr;&darr;&darr;&darr;&darr;</div>

              {/* Row 2: Event Bus */}
              <div className="flex items-center gap-2 mb-3">
                <span className="px-3 py-1.5 rounded-md bg-[#28272b] border border-[#3c3a41] text-white">
                  asyncio.Queue <span className="text-[#858189]">(event bus)</span>
                </span>
              </div>

              <div className="text-[#656169] mb-3 pl-4">&darr;</div>

              {/* Row 3: Analysis */}
              <div className="flex items-center gap-2 mb-3">
                <span className="px-3 py-1.5 rounded-md bg-[#bfa1f5]/10 border border-[#bfa1f5]/20 text-[#bfa1f5]">
                  Gemini 2.5 Flash Lite
                </span>
                <span className="text-[#858189]">&rarr; calls 85+ Boba tools &rarr;</span>
                <span className="px-2 py-1 rounded-md bg-[#84f593]/10 text-[#84f593] border border-[#84f593]/20">
                  {"{"} conviction, direction, asset, size {"}"}
                </span>
              </div>

              <div className="text-[#656169] mb-3 pl-4">&darr;</div>

              {/* Row 4: Risk */}
              <div className="flex items-center gap-2 mb-3">
                <span className="px-3 py-1.5 rounded-md bg-[#F59E0B]/10 border border-[#F59E0B]/20 text-[#F59E0B]">
                  Risk Engine
                </span>
                <span className="text-[#858189]">&rarr; 5 layers &rarr;</span>
                <span className="px-2 py-1 rounded-md bg-[#84f593]/10 text-[#84f593] text-[10px]">PASS</span>
                <span className="text-[#858189]">or</span>
                <span className="px-2 py-1 rounded-md bg-[#f2685f]/10 text-[#f2685f] text-[10px]">REJECT</span>
              </div>

              <div className="text-[#656169] mb-3 pl-4">&darr;</div>

              {/* Row 5: Execution */}
              <div className="flex items-center gap-2 mb-3 flex-wrap">
                <span className="px-3 py-1.5 rounded-md bg-[#84f593]/10 border border-[#84f593]/20 text-[#84f593]">
                  Hyperliquid
                </span>
                <span className="text-[#858189]">&rarr;</span>
                <span className="text-[#bfa1f5]">hl_update_leverage</span>
                <span className="text-[#858189]">&rarr;</span>
                <span className="text-[#bfa1f5]">hl_place_order</span>
                <span className="text-[#858189]">&rarr;</span>
                <span className="text-[#bfa1f5]">hl_get_fills</span>
                <span className="text-[#858189]">&rarr;</span>
                <span className="text-[#bfa1f5]">SL + TP</span>
              </div>

              <div className="text-[#656169] mb-3 pl-4">&darr;</div>

              {/* Row 6: Management */}
              <div className="flex items-center gap-2 mb-3 flex-wrap">
                <span className="px-3 py-1.5 rounded-md bg-[#f2685f]/10 border border-[#f2685f]/20 text-[#f2685f]">
                  Position Manager
                </span>
                <span className="text-[#858189]">&rarr; trailing stop, planned exit, early exit, hard age limit</span>
              </div>

              <div className="text-[#656169] mb-3 pl-4">&darr;</div>

              {/* Row 7: Dashboard */}
              <div className="flex items-center gap-2">
                <span className="px-3 py-1.5 rounded-md bg-[#28272b] border border-[#3c3a41] text-white">
                  Next.js Dashboard
                </span>
                <span className="text-[#858189]">&rarr; real-time equity curve, trade log, signal history, whale feed</span>
              </div>
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            12. CTA + FOOTER
            ══════════════════════════════════════════════════ */}
        <section className="text-center py-16 border-t border-[#3c3a41]">
          <h3 className="text-2xl font-bold mb-3 text-white" style={{ fontFamily: "'Sora', sans-serif" }}>What Boba Makes Possible</h3>
          <p className="text-sm text-[#b8b5bb] leading-relaxed max-w-xl mx-auto mb-3" style={{ fontFamily: "'Inter', sans-serif" }}>
            Without Boba: dozens of APIs, SDKs, auth flows, rate limits, chain-specific logic, and weeks of integration work.
          </p>
          <p className="text-sm text-[#bfa1f5] font-medium max-w-xl mx-auto mb-8" style={{ fontFamily: "'Inter', sans-serif" }}>
            With Boba: one MCP connection, one protocol, 85+ tools, 9 blockchains. SignalFlow was built in days, not months.
          </p>
          <div className="flex justify-center gap-3 flex-wrap">
            <Link
              href="/dashboard"
              className="px-7 py-3 bg-[#bfa1f5] text-[#141316] text-sm font-semibold rounded-full hover:bg-[#d4bef8] transition-colors"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              Explore Dashboard
            </Link>
            <a
              href="https://boba.xyz"
              target="_blank"
              rel="noopener noreferrer"
              className="px-7 py-3 border border-[#3c3a41] text-sm font-semibold rounded-full hover:border-[#656169] transition-colors text-[#b8b5bb]"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              boba.xyz
            </a>
            <a
              href="https://agents.boba.xyz"
              target="_blank"
              rel="noopener noreferrer"
              className="px-7 py-3 border border-[#3c3a41] text-sm font-semibold rounded-full hover:border-[#656169] transition-colors text-[#b8b5bb]"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              Boba Agents Docs
            </a>
          </div>
        </section>

        {/* Footer */}
        <footer className="text-center text-xs text-[#656169] pb-8" style={{ fontFamily: "'Inter', sans-serif" }}>
          SignalFlow &mdash; Autonomous AI Trading Agent &bull; Powered by Boba Agents MCP &bull; Paper trading only &bull; Not financial advice
        </footer>
      </div>
    </div>
  );
}
