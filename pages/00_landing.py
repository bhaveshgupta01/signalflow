"""SignalFlow — Landing page: project overview, architecture, and capabilities."""

import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from styles.theme import apply_theme, COLORS

apply_theme()

# ── Custom CSS for landing page ──────────────────────────────────────────────

st.markdown(
    f"""
    <style>
    .hero-title {{
        font-size: 3.2rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1.1;
        margin-bottom: 0;
    }}
    .hero-title .boba {{
        background: linear-gradient(135deg, #6c63ff, #29b6f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .hero-subtitle {{
        font-size: 1.15rem;
        color: {COLORS["muted"]};
        line-height: 1.5;
        margin-top: 12px;
        max-width: 720px;
    }}
    .hero-badge {{
        display: inline-block;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 3px 12px;
        border-radius: 20px;
        letter-spacing: 0.06em;
        margin-right: 6px;
        margin-bottom: 6px;
    }}
    .badge-boba {{
        background: linear-gradient(135deg, #6c63ff, #29b6f6);
        color: #fff;
    }}
    .badge-live {{
        background: {COLORS["up"]};
        color: #0e1117;
    }}
    .badge-ai {{
        background: rgba(255,171,64,0.15);
        border: 1px solid rgba(255,171,64,0.3);
        color: #ffab40;
    }}
    .section-label {{
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: {COLORS["accent"]};
        margin-bottom: 8px;
    }}
    .arch-card {{
        background: {COLORS["card"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 14px;
        padding: 20px 22px;
        height: 100%;
    }}
    .arch-card h4 {{
        margin: 0 0 6px 0;
        font-size: 1rem;
        color: {COLORS["text"]};
    }}
    .arch-card p {{
        margin: 0;
        font-size: 0.82rem;
        color: {COLORS["muted"]};
        line-height: 1.5;
    }}
    .arch-card .icon {{
        font-size: 1.6rem;
        margin-bottom: 10px;
    }}
    .tool-pill {{
        display: inline-block;
        background: rgba(108,99,255,0.12);
        border: 1px solid rgba(108,99,255,0.25);
        border-radius: 6px;
        padding: 3px 10px;
        font-size: 0.74rem;
        font-family: "SF Mono", "Fira Code", monospace;
        color: {COLORS["accent"]};
        margin: 2px 4px 2px 0;
    }}
    .stat-big {{
        font-size: 2.4rem;
        font-weight: 800;
        color: {COLORS["text"]};
        line-height: 1;
    }}
    .stat-label {{
        font-size: 0.76rem;
        color: {COLORS["muted"]};
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }}
    .flow-step {{
        background: {COLORS["card"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 10px;
        padding: 14px 16px;
        text-align: center;
    }}
    .flow-step .step-num {{
        font-size: 0.68rem;
        font-weight: 700;
        color: {COLORS["accent"]};
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }}
    .flow-step .step-title {{
        font-size: 0.92rem;
        font-weight: 700;
        color: {COLORS["text"]};
        margin-bottom: 4px;
    }}
    .flow-step .step-desc {{
        font-size: 0.76rem;
        color: {COLORS["muted"]};
        line-height: 1.4;
    }}
    .flow-arrow {{
        text-align: center;
        font-size: 1.4rem;
        color: {COLORS["accent"]};
        padding-top: 20px;
    }}
    .boba-highlight {{
        background: linear-gradient(145deg, rgba(108,99,255,0.08), rgba(41,182,246,0.06));
        border: 1px solid rgba(108,99,255,0.2);
        border-radius: 16px;
        padding: 28px 32px;
    }}
    .boba-highlight h3 {{
        background: linear-gradient(135deg, #6c63ff, #29b6f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.4rem;
        margin: 0 0 8px 0;
    }}
    .tech-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 10px;
    }}
    .tech-item {{
        background: {COLORS["card"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 10px;
        padding: 12px 16px;
    }}
    .tech-item .tech-name {{
        font-weight: 700;
        font-size: 0.88rem;
        color: {COLORS["text"]};
    }}
    .tech-item .tech-role {{
        font-size: 0.76rem;
        color: {COLORS["muted"]};
        margin-top: 2px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# HERO
# =============================================================================

st.markdown(
    """
    <div style="margin-bottom: 8px;">
        <span class="hero-badge badge-boba">POWERED BY BOBA</span>
        <span class="hero-badge badge-ai">GEMINI 2.5 FLASH</span>
        <span class="hero-badge badge-live">EVENT-DRIVEN</span>
    </div>
    <div class="hero-title">
        Signal<span style="color:#6c63ff;">Flow</span>
    </div>
    <div class="hero-subtitle">
        An autonomous AI trading agent that monitors prediction markets, tracks whale wallets,
        and executes perpetual futures trades &mdash; all powered by
        <span class="boba">Boba Agents MCP</span>.
        Built to demonstrate what's possible when you give an AI agent
        access to 85+ on-chain trading tools through a single protocol.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# KEY NUMBERS
# =============================================================================

st.markdown('<div class="section-label">AT A GLANCE</div>', unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)
stats_data = [
    ("85+", "Boba Tools", c1),
    ("6", "Async Triggers", c2),
    ("9", "Blockchains", c3),
    ("5", "Dashboard Pages", c4),
    ("$100", "Paper Wallet", c5),
]
for val, label, col in stats_data:
    with col:
        st.markdown(
            f'<div style="background:{COLORS["card"]};border:1px solid {COLORS["border"]};'
            f'border-radius:12px;padding:18px 16px;text-align:center;">'
            f'<div class="stat-big">{val}</div>'
            f'<div class="stat-label">{label}</div></div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# BOBA AGENTS MCP — HIGHLIGHTED SECTION
# =============================================================================

st.markdown('<div class="section-label">THE ENGINE</div>', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="boba-highlight">
        <h3>Boba Agents MCP</h3>
        <p style="font-size:0.95rem;color:{COLORS["text"]};line-height:1.6;margin-bottom:16px;">
            Boba is a <strong>Model Context Protocol (MCP) server</strong> that exposes
            <strong>85+ trading tools</strong> across <strong>9 blockchains</strong> through a single,
            standardized interface. Instead of integrating dozens of exchange APIs, DEX SDKs, and
            on-chain indexers individually, SignalFlow connects to one MCP endpoint and gets
            instant access to everything &mdash; prediction markets, perpetual futures, wallet
            tracking, token discovery, cross-chain pricing, and more.
        </p>
        <p style="font-size:0.85rem;color:{COLORS["muted"]};line-height:1.5;margin-bottom:18px;">
            Boba handles authentication, rate limiting, chain routing, and data normalization.
            The AI agent (Gemini 2.5 Flash) receives all 85 tools as callable functions &mdash;
            it can autonomously decide which tools to use, chain calls together, and extract
            exactly the data it needs to make trading decisions.
        </p>
        <div style="font-size:0.76rem;font-weight:700;color:{COLORS["accent"]};letter-spacing:0.06em;
            text-transform:uppercase;margin-bottom:10px;">Tools used by SignalFlow</div>
        <div>
            <span class="tool-pill">pm_search_markets</span>
            <span class="tool-pill">pm_get_price_history</span>
            <span class="tool-pill">pm_get_top_holders</span>
            <span class="tool-pill">pm_get_comments</span>
            <span class="tool-pill">hl_get_asset</span>
            <span class="tool-pill">hl_get_markets</span>
            <span class="tool-pill">hl_place_order</span>
            <span class="tool-pill">hl_update_leverage</span>
            <span class="tool-pill">hl_get_predicted_funding</span>
            <span class="tool-pill">hl_get_open_orders</span>
            <span class="tool-pill">hl_get_positions</span>
            <span class="tool-pill">get_kol_swaps</span>
            <span class="tool-pill">search_tokens</span>
            <span class="tool-pill">get_token_info</span>
            <span class="tool-pill">audit_token</span>
            <span class="tool-pill">get_portfolio</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# HOW IT WORKS — PIPELINE FLOW
# =============================================================================

st.markdown(
    '<div class="section-label">HOW IT WORKS</div>', unsafe_allow_html=True
)
st.markdown(
    f'<p style="font-size:0.9rem;color:{COLORS["muted"]};margin-bottom:16px;">'
    "Six independent triggers scan different data sources in parallel. When a signal "
    "crosses the threshold, it enters the event bus and flows through the agent pipeline.</p>",
    unsafe_allow_html=True,
)

# Pipeline steps
steps = [
    ("Phase 1", "Scan", "6 async triggers poll Polymarket, KOL wallets, funding rates, "
     "token trends, and cross-chain prices every 45s-5m."),
    ("Phase 2", "Analyze", "Gemini 2.5 Flash evaluates each signal using all 85 Boba tools. "
     "Returns conviction score, direction, asset, and sizing."),
    ("Phase 3", "Risk Gate", "Deterministic checks enforce position limits, margin, "
     "stop-loss/take-profit, and max exposure. No LLM can override."),
    ("Phase 4", "Execute", "Trades are placed on Hyperliquid perps via Boba's hl_place_order "
     "with automatic SL and TP orders."),
    ("Phase 5", "Manage", "Open positions are monitored every cycle. Auto-close on SL/TP hit "
     "or after 4 hours. PnL is tracked per trade."),
]

cols = st.columns(9)  # 5 steps + 4 arrows
col_idx = 0
for i, (phase, title, desc) in enumerate(steps):
    with cols[col_idx]:
        st.markdown(
            f'<div class="flow-step">'
            f'<div class="step-num">{phase}</div>'
            f'<div class="step-title">{title}</div>'
            f'<div class="step-desc">{desc}</div></div>',
            unsafe_allow_html=True,
        )
    col_idx += 1
    if i < len(steps) - 1:
        with cols[col_idx]:
            st.markdown(
                '<div class="flow-arrow">&rarr;</div>', unsafe_allow_html=True
            )
        col_idx += 1

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# TRADING STRATEGIES
# =============================================================================

st.markdown(
    '<div class="section-label">TRADING STRATEGIES</div>', unsafe_allow_html=True
)

strategies = [
    (
        "Prediction Market Signals",
        "Scans Polymarket for 3%+ price moves on crypto-related prediction markets. "
        "Interprets sentiment shifts and trades directionally on Hyperliquid perps.",
        "pm_search_markets, pm_get_price_history",
    ),
    (
        "KOL Whale Tracking",
        "Monitors smart-money wallets for trades >$100. When a whale trades an asset "
        "in the same direction as a signal, conviction gets a +15% boost.",
        "get_kol_swaps",
    ),
    (
        "Funding Rate Arbitrage",
        "Detects when Hyperliquid funding rates diverge >0.01% from other exchanges. "
        "Trades the spread before rates converge.",
        "hl_get_predicted_funding",
    ),
    (
        "Token Discovery",
        "Finds tokens with >50% 24h change and >$100k volume. Evaluates momentum "
        "and security before recommending a trade.",
        "search_tokens, get_token_info, audit_token",
    ),
    (
        "Cross-Chain Arbitrage",
        "Identifies 0.3%+ price differences for the same token across blockchains. "
        "Surfaces opportunities before the spread closes.",
        "cross-chain price tools",
    ),
]

s1, s2 = st.columns(2)
for i, (name, desc, tools) in enumerate(strategies):
    col = s1 if i % 2 == 0 else s2
    with col:
        st.markdown(
            f'<div style="background:{COLORS["card"]};border:1px solid {COLORS["border"]};'
            f'border-left:3px solid {COLORS["accent"]};border-radius:10px;'
            f'padding:16px 20px;margin-bottom:10px;">'
            f'<div style="font-weight:700;font-size:0.92rem;color:{COLORS["text"]};'
            f'margin-bottom:6px;">{name}</div>'
            f'<div style="font-size:0.82rem;color:{COLORS["muted"]};line-height:1.5;'
            f'margin-bottom:8px;">{desc}</div>'
            f'<div style="font-size:0.72rem;color:{COLORS["accent"]};'
            f'font-family:monospace;">Boba tools: {tools}</div></div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# ARCHITECTURE OVERVIEW
# =============================================================================

st.markdown(
    '<div class="section-label">ARCHITECTURE</div>', unsafe_allow_html=True
)

arch_items = [
    ("AI Brain", "Gemini 2.5 Flash via Google Vertex AI. Full function-calling access to all "
     "85 Boba tools. Returns structured JSON decisions with conviction scores."),
    ("Event Bus", "asyncio.Queue connects 6 independent triggers to a single agent loop. "
     "Events are processed in order with backpressure handling."),
    ("Risk Engine", "Pure Python, zero LLM involvement. Enforces margin checks, position "
     "limits, stop-loss/take-profit, max exposure, and trade minimums ($15)."),
    ("Database", "SQLite with WAL mode. 7 tables, 7 indexes. Handles concurrent reads "
     "from the dashboard and writes from the agent without locks."),
    ("Dashboard", "Streamlit + Plotly. 5 interactive pages with dark theme, auto-refresh "
     "every 10s. Real-time portfolio tracking and signal visualization."),
    ("Deployment", "Docker multi-stage build (Node.js + Python). docker-compose runs "
     "agent and dashboard as separate services. Production-ready."),
]

a1, a2, a3 = st.columns(3)
arch_cols = [a1, a2, a3]
for i, (title, desc) in enumerate(arch_items):
    with arch_cols[i % 3]:
        st.markdown(
            f'<div class="arch-card">'
            f'<h4>{title}</h4>'
            f'<p>{desc}</p></div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# TECH STACK
# =============================================================================

st.markdown(
    '<div class="section-label">TECH STACK</div>', unsafe_allow_html=True
)

techs = [
    ("Boba Agents MCP", "Trading infrastructure (85+ tools, 9 chains)"),
    ("Gemini 2.5 Flash", "AI decision engine with function calling"),
    ("Hyperliquid", "Perpetual futures exchange (execution)"),
    ("Polymarket", "Prediction markets (signal source)"),
    ("Streamlit", "Dashboard framework (5 pages)"),
    ("Plotly", "Interactive charts & visualizations"),
    ("SQLite (WAL)", "Persistent storage (7 tables)"),
    ("Pydantic v2", "Data validation & type safety"),
    ("asyncio", "Concurrent trigger execution"),
    ("Docker", "Containerized deployment"),
]

tech_html = '<div class="tech-grid">'
for name, role in techs:
    tech_html += (
        f'<div class="tech-item">'
        f'<div class="tech-name">{name}</div>'
        f'<div class="tech-role">{role}</div></div>'
    )
tech_html += "</div>"
st.markdown(tech_html, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# RISK PARAMETERS
# =============================================================================

st.markdown(
    '<div class="section-label">RISK PARAMETERS</div>', unsafe_allow_html=True
)

r1, r2, r3, r4 = st.columns(4)
risk_params = [
    ("4%", "Stop-Loss", "Auto-exit losing trades at 4% drawdown", r1),
    ("10%", "Take-Profit", "Lock in gains at 10% price target", r2),
    ("3x", "Max Leverage", "Hard cap on leverage, enforced in code", r3),
    ("4h", "Max Hold Time", "Positions auto-close after 4 hours", r4),
]

for val, label, desc, col in risk_params:
    with col:
        st.markdown(
            f'<div style="background:{COLORS["card"]};border:1px solid {COLORS["border"]};'
            f'border-radius:12px;padding:18px 16px;text-align:center;">'
            f'<div class="stat-big">{val}</div>'
            f'<div style="font-weight:700;font-size:0.85rem;color:{COLORS["text"]};'
            f'margin-top:4px;">{label}</div>'
            f'<div style="font-size:0.76rem;color:{COLORS["muted"]};margin-top:4px;">'
            f'{desc}</div></div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# WHAT BOBA ENABLES — CTA
# =============================================================================

st.markdown(
    f"""
    <div style="background:linear-gradient(145deg, rgba(108,99,255,0.06), rgba(41,182,246,0.04));
        border:1px solid rgba(108,99,255,0.15);border-radius:16px;padding:28px 32px;
        text-align:center;">
        <div style="font-size:1.2rem;font-weight:700;color:{COLORS["text"]};margin-bottom:8px;">
            What Boba Makes Possible
        </div>
        <div style="font-size:0.9rem;color:{COLORS["muted"]};line-height:1.6;max-width:700px;
            margin:0 auto 20px auto;">
            Without Boba, building SignalFlow would mean integrating Polymarket's REST API,
            Hyperliquid's WebSocket feeds, multiple DEX SDKs, wallet indexers, and on-chain
            data providers &mdash; each with its own auth, rate limits, and data formats.
            <br><br>
            With Boba, it's <strong style="color:{COLORS["text"]};">one connection, one protocol,
            85+ tools</strong>. The AI agent calls <code style="color:{COLORS["accent"]};">
            pm_search_markets</code> to scan predictions, <code style="color:{COLORS["accent"]};">
            hl_place_order</code> to trade perps, and <code style="color:{COLORS["accent"]};">
            get_kol_swaps</code> to track whales &mdash; all through the same MCP interface.
        </div>
        <div style="display:inline-block;background:linear-gradient(135deg, #6c63ff, #29b6f6);
            color:#fff;font-size:0.82rem;font-weight:700;padding:8px 24px;border-radius:8px;
            letter-spacing:0.03em;">
            Built on Boba Agents MCP &mdash; agent.boba.xyz
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# FOOTER
# =============================================================================

st.markdown(
    f"""
    <div style="text-align:center;padding:16px 0;border-top:1px solid {COLORS["border"]};">
        <div style="font-size:0.78rem;color:{COLORS["muted"]};">
            SignalFlow &mdash; Event-driven AI trading agent
            &bull; Powered by Boba Agents MCP
            &bull; Paper trading only &bull; $100 virtual wallet
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
