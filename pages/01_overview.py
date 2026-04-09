import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import datetime

from styles.theme import apply_theme, COLORS
from db import (
    get_recent_decisions,
    get_recent_signals,
    get_recent_analyses,
    get_open_positions,
    get_stats,
)
from config import MAX_PORTFOLIO_EXPOSURE_USD, MAX_CONCURRENT_POSITIONS

apply_theme()

# ── Data ─────────────────────────────────────────────────────────────────────

stats = get_stats()
signals = get_recent_signals(minutes=60)
analyses = get_recent_analyses(limit=10)
open_pos = get_open_positions()
decisions = get_recent_decisions(limit=50)

# Count from actual tables
from db import _get_conn
_c = _get_conn()
total_signals = _c.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
total_analyses = _c.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
total_trades = stats["total_trades"]

# ═══════════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════════

st.header("Command Center")
st.markdown(
    '<div style="display:inline-block;background:#00e676;color:#0e1117;'
    'font-size:0.68rem;font-weight:700;padding:2px 10px;border-radius:12px;'
    'margin-bottom:4px;">LIVE</div>',
    unsafe_allow_html=True,
)
st.caption(
    "SignalFlow's brain -- see how the AI agent monitors markets, analyzes "
    "signals, and makes trading decisions in real-time."
)

# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE STATUS
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("Pipeline Status")
st.caption(
    "Each stage runs in sequence: signals are detected, analyzed by AI, "
    "checked against risk limits, executed as trades, then managed until close."
)

stages = [
    ("TRIGGERS", str(total_signals), "detected",
     "Scans Polymarket prediction markets and KOL wallets for significant price moves."),
    ("ANALYZER", str(total_analyses), "produced",
     "Gemini 2.5 Flash evaluates each signal for trade-worthiness and assigns a conviction score."),
    ("RISK", str(total_analyses), "evaluated",
     "Checks position sizing, exposure limits, and stop-loss/take-profit levels."),
    ("EXECUTOR", str(total_trades), "executed",
     "Places trades on Hyperliquid perpetuals when conviction exceeds the threshold."),
    ("MANAGER", str(len(open_pos)), "open",
     "Monitors open positions, enforces SL/TP, and closes trades when targets are hit."),
]

cols = st.columns(len(stages))
for i, (name, value, unit, help_text) in enumerate(stages):
    with cols[i]:
        st.metric(label=name, value=value, delta=unit, help=help_text)

st.caption("TRIGGERS  -->  ANALYZER  -->  RISK  -->  EXECUTOR  -->  MANAGER")

# ═══════════════════════════════════════════════════════════════════════════════
# BOBA API CONNECTIONS
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("Boba API Connections")
st.caption(
    "External data sources the agent connects to via the Boba MCP server. "
    "Each tool group provides a different market intelligence feed."
)

boba_tools = [
    ("Polymarket Scanner", "pm_*",
     "Monitors prediction market prices for sharp moves that may signal real-world events."),
    ("KOL Wallet Tracker", "get_kol*",
     "Watches whale and influencer wallets for large trades that reveal smart-money positioning."),
    ("Funding Rate Monitor", "hl_funding*",
     "Tracks perpetual swap funding rates to detect crowded positions and reversal setups."),
    ("Cross-Chain Arb", "crosschain_*",
     "Compares token prices across chains to find mispricing and arbitrage opportunities."),
]

bcols = st.columns(len(boba_tools))
for i, (name, prefix, desc) in enumerate(boba_tools):
    with bcols[i]:
        st.markdown(
            f'<div style="background:{COLORS["card"]};border:1px solid {COLORS["border"]};'
            f'border-radius:10px;padding:14px 16px;">'
            f'<div style="font-weight:700;font-size:0.9rem;color:{COLORS["text"]};'
            f'margin-bottom:4px;">{name}</div>'
            f'<div style="font-size:0.72rem;color:{COLORS["accent"]};margin-bottom:6px;'
            f'font-family:monospace;">{prefix}</div>'
            f'<div style="font-size:0.78rem;color:{COLORS["muted"]};line-height:1.4;">'
            f'{desc}</div></div>',
            unsafe_allow_html=True,
        )

# ═══════════════════════════════════════════════════════════════════════════════
# KEY METRICS
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("Key Metrics")
st.caption("High-level performance numbers across all trades, updated every agent cycle.")

m1, m2, m3, m4 = st.columns(4)

pnl = stats["total_pnl"]
pnl_sign = "+" if pnl >= 0 else ""
m1.metric("Total PnL", f"${pnl:,.2f}", delta=f"{pnl_sign}${pnl:,.2f}")

wr = stats["win_rate"]
m2.metric(
    "Win Rate", f"{wr:.1f}%",
    delta=f"{stats['wins']}W / {stats['closed_trades'] - stats['wins']}L",
)

m3.metric(
    "Open Positions", f"{len(open_pos)}",
    delta=f"of {MAX_CONCURRENT_POSITIONS} max",
)

exp = stats["open_exposure"]
m4.metric(
    "Exposure", f"${exp:,.0f}",
    delta=f"of ${MAX_PORTFOLIO_EXPOSURE_USD:,.0f} limit",
)

# ═══════════════════════════════════════════════════════════════════════════════
# RECENT SIGNALS + AI REASONING
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Recent Signals")
    st.caption("Latest price movements the agent detected in the last hour.")

    if not signals:
        st.info("No signals detected recently. The agent is scanning for moves...")
    else:
        for s in signals[:8]:
            direction_str = "+" if s.price_change_pct >= 0 else ""
            color = COLORS["up"] if s.price_change_pct >= 0 else COLORS["down"]
            det = s.detected_at.replace(tzinfo=None) if s.detected_at.tzinfo else s.detected_at
            ago = (datetime.utcnow() - det).total_seconds() / 60
            st.markdown(
                f'<div style="background:{COLORS["card"]};border-left:3px solid {COLORS["accent"]};'
                f'border-radius:8px;padding:10px 14px;margin-bottom:6px;">'
                f'<div style="font-weight:600;font-size:0.86rem;color:{COLORS["text"]};'
                f'line-height:1.35;">{s.market_question[:80]}</div>'
                f'<div style="font-size:0.74rem;color:{COLORS["muted"]};margin-top:3px;">'
                f'Price: {s.current_price:.2f} | '
                f'<span style="color:{color};font-weight:700;">'
                f'{direction_str}{s.price_change_pct:.1f}%</span> | '
                f'{ago:.0f}m ago</div></div>',
                unsafe_allow_html=True,
            )

with right_col:
    st.subheader("AI Reasoning")
    st.caption("How the agent analyzed each signal and what it decided to do.")

    if not analyses:
        st.info(
            "No analyses yet. Waiting for signals above the conviction threshold..."
        )
    else:
        for a in analyses[:6]:
            conv_label = f"{a.conviction_score:.0%} conviction"
            dir_label = a.suggested_direction.value.upper()
            with st.expander(
                f"{dir_label} {a.suggested_asset} | {conv_label} | "
                f"${a.suggested_size_usd:.0f}"
            ):
                st.write(a.reasoning)
                if a.risk_notes:
                    st.caption(f"Risk notes: {a.risk_notes}")
                st.caption(
                    f"Analyzed at {a.created_at.strftime('%Y-%m-%d %H:%M')}"
                )

# ═══════════════════════════════════════════════════════════════════════════════
# RISK UTILIZATION
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("Risk Utilization")
st.caption(
    "How much of the agent's risk budget is currently in use. "
    "Exposure is the total USD committed to open trades. "
    "Positions is the number of concurrent trades the agent is managing."
)

exposure_pct = (
    min(stats["open_exposure"] / MAX_PORTFOLIO_EXPOSURE_USD, 1.0)
    if MAX_PORTFOLIO_EXPOSURE_USD > 0
    else 0.0
)
position_pct = (
    min(len(open_pos) / MAX_CONCURRENT_POSITIONS, 1.0)
    if MAX_CONCURRENT_POSITIONS > 0
    else 0.0
)

st.write(
    f"**Portfolio Exposure** -- "
    f"${stats['open_exposure']:,.0f} / ${MAX_PORTFOLIO_EXPOSURE_USD:,.0f}"
)
st.progress(exposure_pct)

st.write(
    f"**Open Positions** -- "
    f"{len(open_pos)} / {MAX_CONCURRENT_POSITIONS}"
)
st.progress(position_pct)
