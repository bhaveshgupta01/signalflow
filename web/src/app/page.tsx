import Link from "next/link";

/* ── Data ─────────────────────────────────────────────── */

const bobaTools = [
  "pm_search_markets", "pm_get_price_history", "pm_get_top_holders",
  "pm_get_comments", "hl_get_asset", "hl_get_markets", "hl_place_order",
  "hl_update_leverage", "hl_get_predicted_funding", "hl_get_open_orders",
  "hl_get_positions", "get_kol_swaps", "search_tokens", "get_token_info",
  "audit_token", "get_portfolio",
];

const lifecycle = [
  {
    step: "01",
    title: "Scan",
    desc: "6 async triggers poll Polymarket, KOL wallets, funding rates, token trends, and cross-chain prices every 45s\u20135m.",
    color: "#8B5CF6",
    tools: ["pm_search_markets", "get_kol_swaps", "hl_get_predicted_funding"],
  },
  {
    step: "02",
    title: "Analyze",
    desc: "Gemini 2.5 Flash evaluates each signal using all 85 Boba tools. Returns conviction score, direction, asset, and sizing.",
    color: "#06B6D4",
    tools: ["pm_get_price_history", "pm_get_top_holders", "pm_get_comments"],
  },
  {
    step: "03",
    title: "Risk Gate",
    desc: "Deterministic checks enforce position limits, margin, stop-loss/take-profit, and max exposure. No LLM can override.",
    color: "#F59E0B",
    tools: [],
  },
  {
    step: "04",
    title: "Execute",
    desc: "Trades placed on Hyperliquid perps via Boba\u2019s hl_place_order with automatic SL and TP orders in a single call.",
    color: "#22C55E",
    tools: ["hl_place_order", "hl_update_leverage"],
  },
  {
    step: "05",
    title: "Manage",
    desc: "Open positions monitored every cycle. Auto-close on SL/TP hit or after 4 hours. Trailing stops on profit.",
    color: "#EF4444",
    tools: ["hl_get_positions", "hl_get_open_orders"],
  },
];

const strategies = [
  { name: "Prediction Markets", desc: "Scans Polymarket for 5%+ price moves on crypto prediction markets. Interprets sentiment shifts and trades directionally.", tools: "pm_search_markets, pm_get_price_history", icon: "M" },
  { name: "KOL Whale Tracking", desc: "Monitors smart-money wallets for trades >$500. Whale alignment gives +15% conviction boost to signals.", tools: "get_kol_swaps", icon: "W" },
  { name: "Funding Rate Arb", desc: "Detects when Hyperliquid funding rates diverge >0.01% from exchanges. Trades the spread before convergence.", tools: "hl_get_predicted_funding", icon: "F" },
  { name: "Token Discovery", desc: "Finds tokens with >50% 24h change and >$100k volume. Evaluates momentum and security before recommending.", tools: "search_tokens, audit_token", icon: "T" },
  { name: "Cross-Chain Arb", desc: "Identifies 0.3%+ price differences for the same token across blockchains before the spread closes.", tools: "get_token_price", icon: "X" },
];

const architecture = [
  { title: "AI Brain", desc: "Gemini 2.5 Flash via Vertex AI with full function-calling access to 85 Boba tools. Structured JSON decisions with conviction scoring.", tag: "gemini" },
  { title: "Event Bus", desc: "asyncio.Queue connects 6 independent triggers to a single agent loop. Events processed in order with backpressure.", tag: "asyncio" },
  { title: "Risk Engine", desc: "Pure Python, zero LLM involvement. Enforces margin, position limits, SL/TP, max exposure, and $20 trade minimums.", tag: "python" },
  { title: "Database", desc: "Supabase Postgres with 7 tables and indexes. Handles concurrent reads from dashboard and writes from agent.", tag: "supabase" },
  { title: "Dashboard", desc: "Next.js + Recharts deployed on Vercel. 5 pages with auto-refresh, dark theme, and real-time portfolio tracking.", tag: "next.js" },
  { title: "Deployment", desc: "Python agent runs on Docker. Dashboard deploys with git push. Supabase handles persistence across both.", tag: "docker" },
];

const techStack = [
  { name: "Boba Agents MCP", role: "85+ tools, 9 chains" },
  { name: "Gemini 2.5 Flash", role: "AI decision engine" },
  { name: "Hyperliquid", role: "Perps execution" },
  { name: "Polymarket", role: "Signal source" },
  { name: "Next.js", role: "Dashboard" },
  { name: "Supabase", role: "Database" },
  { name: "Recharts", role: "Visualizations" },
  { name: "Pydantic v2", role: "Data models" },
  { name: "asyncio", role: "Concurrency" },
  { name: "Docker", role: "Deployment" },
];

const riskParams = [
  { val: "3%", label: "Stop-Loss" },
  { val: "8%", label: "Take-Profit" },
  { val: "3x", label: "Max Leverage" },
  { val: "4h", label: "Max Hold" },
  { val: "5", label: "Max Positions" },
  { val: "$1k", label: "Max Exposure" },
];

const stats = [
  { val: "85+", label: "Boba Tools" },
  { val: "6", label: "Async Triggers" },
  { val: "9", label: "Blockchains" },
  { val: "$100", label: "Paper Wallet" },
];

/* ── Page ─────────────────────────────────────────────── */

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-sf-bg">
      {/* ── Nav bar ───────────────────────────────────── */}
      <nav className="sticky top-0 z-40 bg-sf-bg/80 backdrop-blur-lg border-b border-sf-border">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-sf-brand/20 flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
            </div>
            <span className="text-sm font-semibold">SignalFlow</span>
          </div>
          <div className="flex items-center gap-4">
            <a href="https://agents.boba.xyz" target="_blank" rel="noopener noreferrer" className="text-xs text-sf-muted hover:text-sf-text-2 transition-colors">
              Boba Docs
            </a>
            <Link
              href="/dashboard"
              className="text-xs font-medium px-3 py-1.5 bg-sf-brand text-white rounded-md hover:bg-sf-brand/90 transition-colors"
            >
              Open Dashboard
            </Link>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-16 space-y-24">

        {/* ── Hero ────────────────────────────────────── */}
        <section className="text-center max-w-3xl mx-auto">
          <div className="flex justify-center gap-2 mb-6">
            <span className="text-[10px] font-semibold px-2.5 py-1 rounded-full bg-sf-brand/15 text-sf-brand tracking-wider uppercase">
              Powered by Boba
            </span>
            <span className="text-[10px] font-semibold px-2.5 py-1 rounded-full bg-sf-warn/15 text-sf-warn tracking-wider uppercase">
              Gemini 2.5 Flash
            </span>
            <span className="text-[10px] font-semibold px-2.5 py-1 rounded-full bg-sf-up/15 text-sf-up tracking-wider uppercase">
              Event-Driven
            </span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-[1.1]">
            AI Trading Agent for
            <br />
            <span className="bg-gradient-to-r from-[#8B5CF6] to-[#06B6D4] bg-clip-text text-transparent">
              Crypto Perpetuals
            </span>
          </h1>
          <p className="text-base text-sf-text-2 leading-relaxed mt-5 max-w-xl mx-auto">
            An autonomous agent that monitors prediction markets, tracks whale wallets,
            and executes perps trades on Hyperliquid &mdash; all through{" "}
            <span className="text-sf-brand font-medium">Boba Agents MCP</span>.
          </p>
          <div className="flex justify-center gap-3 mt-8">
            <Link
              href="/dashboard"
              className="px-5 py-2.5 bg-sf-brand text-white text-sm font-medium rounded-lg hover:bg-sf-brand/90 transition-colors"
            >
              View Dashboard
            </Link>
            <a
              href="https://agents.boba.xyz"
              target="_blank"
              rel="noopener noreferrer"
              className="px-5 py-2.5 bg-sf-card border border-sf-border text-sm font-medium rounded-lg hover:border-sf-border-bold hover:bg-sf-card-alt transition-colors"
            >
              Boba Agents
            </a>
          </div>
        </section>

        {/* ── Stats bar ──────────────────────────────── */}
        <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {stats.map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-2xl font-bold tabular-nums">{s.val}</div>
              <div className="text-xs text-sf-muted uppercase tracking-wider mt-0.5">{s.label}</div>
            </div>
          ))}
        </section>

        {/* ── Agent Lifecycle ─────────────────────────── */}
        <section>
          <SectionHeader
            tag="How It Works"
            title="Agent Lifecycle"
            desc="Six independent triggers scan data sources in parallel. When a signal crosses the threshold, it enters the event bus and flows through the pipeline."
          />

          {/* Flow diagram */}
          <div className="mt-10 space-y-4">
            {lifecycle.map((phase, i) => (
              <div key={phase.step} className="flex gap-4 items-start">
                {/* Step indicator */}
                <div className="flex flex-col items-center flex-shrink-0 pt-1">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold"
                    style={{ background: `${phase.color}15`, color: phase.color }}
                  >
                    {phase.step}
                  </div>
                  {i < lifecycle.length - 1 && (
                    <div className="w-px h-full min-h-8 bg-sf-border mt-1" />
                  )}
                </div>

                {/* Content */}
                <div className="bg-sf-card border border-sf-border rounded-lg p-4 flex-1 hover:border-sf-border-bold transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-sf-text">{phase.title}</h3>
                    {phase.step === "03" && (
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-sf-warn/10 text-sf-warn">NO LLM</span>
                    )}
                  </div>
                  <p className="text-sm text-sf-text-2 leading-relaxed">{phase.desc}</p>
                  {phase.tools.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {phase.tools.map((t) => (
                        <code key={t} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sf-brand/8 text-sf-brand border border-sf-brand/15">
                          {t}
                        </code>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Boba MCP Engine ─────────────────────────── */}
        <section>
          <SectionHeader
            tag="The Engine"
            title="Boba Agents MCP"
            desc="One MCP endpoint. 85+ tools. 9 blockchains. Boba handles authentication, rate limiting, chain routing, and data normalization. The AI agent receives all tools as callable functions."
          />

          <div className="mt-8 bg-sf-card border border-sf-border rounded-lg p-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">What Boba Provides</h4>
                <ul className="space-y-2 text-sm text-sf-text-2">
                  {[
                    "Prediction market data (Polymarket)",
                    "Perpetual futures execution (Hyperliquid)",
                    "KOL wallet monitoring (429 wallets)",
                    "Token discovery & security audits",
                    "Cross-chain price comparison",
                    "Portfolio & position management",
                  ].map((item) => (
                    <li key={item} className="flex items-start gap-2">
                      <svg className="w-4 h-4 text-sf-up flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-3">Tools Used</h4>
                <div className="flex flex-wrap gap-1.5">
                  {bobaTools.map((t) => (
                    <code key={t} className="text-[10px] font-mono px-2 py-1 rounded bg-sf-brand/8 text-sf-brand border border-sf-brand/15">
                      {t}
                    </code>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* API flow visualization */}
          <div className="mt-4 bg-sf-surface border border-sf-border rounded-lg p-6">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-4">Execution Flow</h4>
            <div className="font-mono text-xs text-sf-text-2 space-y-1 leading-relaxed">
              <div><span className="text-sf-muted">1.</span> Agent receives signal from event bus</div>
              <div><span className="text-sf-muted">2.</span> Calls <span className="text-sf-brand">pm_get_price_history</span> + <span className="text-sf-brand">pm_get_top_holders</span> via Boba</div>
              <div><span className="text-sf-muted">3.</span> Gemini analyzes with all 85 tools available as functions</div>
              <div><span className="text-sf-muted">4.</span> Returns: <span className="text-sf-up">{'{'} direction: "long", conviction: 0.78, asset: "BTC", size: 50 {'}'}</span></div>
              <div><span className="text-sf-muted">5.</span> Risk engine validates margin, exposure, position limits</div>
              <div><span className="text-sf-muted">6.</span> Calls <span className="text-sf-brand">hl_place_order</span> with market + SL + TP in one call</div>
            </div>
          </div>
        </section>

        {/* ── Trading Strategies ──────────────────────── */}
        <section>
          <SectionHeader
            tag="Strategies"
            title="Trading Strategies"
            desc="Five parallel strategies scan different data sources for trading opportunities."
          />
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {strategies.map((s) => (
              <div
                key={s.name}
                className="bg-sf-card border border-sf-border rounded-lg p-4 hover:border-sf-border-bold transition-colors"
              >
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-7 h-7 rounded-md bg-sf-brand/10 flex items-center justify-center text-xs font-bold text-sf-brand">
                    {s.icon}
                  </div>
                  <h3 className="font-semibold text-sm text-sf-text">{s.name}</h3>
                </div>
                <p className="text-xs text-sf-text-2 leading-relaxed mb-2">{s.desc}</p>
                <div className="flex flex-wrap gap-1">
                  {s.tools.split(", ").map((t) => (
                    <code key={t} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-sf-brand/8 text-sf-brand">
                      {t}
                    </code>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Architecture ────────────────────────────── */}
        <section>
          <SectionHeader
            tag="Architecture"
            title="System Components"
            desc="Modular architecture with clear separation of concerns."
          />
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {architecture.map((a) => (
              <div key={a.title} className="bg-sf-card border border-sf-border rounded-lg p-4 hover:border-sf-border-bold transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-sm text-sf-text">{a.title}</h4>
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-sf-card-alt text-sf-muted uppercase">
                    {a.tag}
                  </span>
                </div>
                <p className="text-xs text-sf-text-2 leading-relaxed">{a.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Risk + Tech Stack row ──────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Risk Parameters */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-4">Risk Parameters</h3>
            <div className="grid grid-cols-3 gap-3">
              {riskParams.map((r) => (
                <div key={r.label} className="bg-sf-card border border-sf-border rounded-lg p-3 text-center">
                  <div className="text-lg font-bold tabular-nums">{r.val}</div>
                  <div className="text-[10px] text-sf-muted uppercase tracking-wider mt-0.5">{r.label}</div>
                </div>
              ))}
            </div>
          </section>

          {/* Tech Stack */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-sf-muted mb-4">Tech Stack</h3>
            <div className="grid grid-cols-2 gap-2">
              {techStack.map((t) => (
                <div key={t.name} className="flex items-center gap-2 bg-sf-card border border-sf-border rounded-lg px-3 py-2">
                  <span className="text-sm font-medium text-sf-text">{t.name}</span>
                  <span className="text-[10px] text-sf-muted">{t.role}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* ── CTA ─────────────────────────────────────── */}
        <section className="text-center py-12 border-t border-sf-border">
          <h3 className="text-xl font-semibold mb-2">What Boba Makes Possible</h3>
          <p className="text-sm text-sf-text-2 leading-relaxed max-w-xl mx-auto mb-6">
            Without Boba: dozens of APIs, SDKs, auth flows, rate limits.
            <br />
            With Boba: <span className="text-sf-brand font-medium">one connection, one protocol, 85+ tools</span>.
          </p>
          <div className="flex justify-center gap-3">
            <Link
              href="/dashboard"
              className="px-5 py-2.5 bg-sf-brand text-white text-sm font-medium rounded-lg hover:bg-sf-brand/90 transition-colors"
            >
              Explore Dashboard
            </Link>
            <a
              href="https://agents.boba.xyz"
              target="_blank"
              rel="noopener noreferrer"
              className="px-5 py-2.5 bg-sf-card border border-sf-border text-sm font-medium rounded-lg hover:border-sf-border-bold transition-colors"
            >
              agents.boba.xyz
            </a>
          </div>
        </section>

        {/* ── Footer ──────────────────────────────────── */}
        <footer className="text-center text-xs text-sf-subtle pb-8">
          SignalFlow &mdash; Event-driven AI trading agent &bull; Powered by Boba Agents MCP &bull; Paper trading only
        </footer>
      </div>
    </div>
  );
}

/* ── Helpers ──────────────────────────────────────────── */

function SectionHeader({ tag, title, desc }: { tag: string; title: string; desc: string }) {
  return (
    <div className="max-w-2xl">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-sf-brand mb-2">{tag}</div>
      <h2 className="text-2xl font-bold text-sf-text">{title}</h2>
      <p className="text-sm text-sf-text-2 leading-relaxed mt-2">{desc}</p>
    </div>
  );
}
