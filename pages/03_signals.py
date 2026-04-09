import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta

from db import init_db, get_recent_signals, get_recent_analyses
from styles.theme import COLORS, apply_theme, plotly_layout

init_db()
apply_theme()

PLOTLY_LAYOUT = plotly_layout()

# ── Header ───────────────────────────────────────────────────────────────────
st.header("Market Scanner")
st.caption(
    "Real-time monitoring of Polymarket prediction markets, KOL whale trades, "
    "and funding rate anomalies. These are the raw inputs the agent processes "
    "to find trading opportunities."
)

# ── Load data ────────────────────────────────────────────────────────────────
TIME_OPTIONS = {"1h": 60, "6h": 360, "24h": 1440, "All": 60 * 24 * 365}

# Sidebar filters
st.sidebar.subheader("Filters")
all_signals = get_recent_signals(minutes=60 * 24 * 365)
categories = sorted({s.category for s in all_signals if s.category})
cat_filter = st.sidebar.selectbox("Category", ["All"] + categories)
time_filter = st.sidebar.selectbox("Time Window", list(TIME_OPTIONS.keys()), index=2)

signals = get_recent_signals(minutes=TIME_OPTIONS[time_filter])
if cat_filter != "All":
    signals = [s for s in signals if s.category == cat_filter]

analyses = get_recent_analyses(limit=500)
analysis_by_signal = {a.signal_id: a for a in analyses}

# ── Summary Metrics ──────────────────────────────────────────────────────────
avg_change = sum(s.price_change_pct for s in signals) / len(signals) if signals else 0
with_analysis = sum(1 for s in signals if s.id in analysis_by_signal)

c1, c2, c3 = st.columns(3)
c1.metric("Total Signals", len(signals))
c2.metric("Avg Price Change", f"{avg_change:+.1f}%")
c3.metric("Signals with AI Analysis", with_analysis)

st.divider()

# ── Signal Type Breakdown ────────────────────────────────────────────────────
st.subheader("Signal Type Breakdown")

if signals:
    cat_counts: dict[str, int] = {}
    for s in signals:
        label = s.category if s.category else "uncategorized"
        cat_counts[label] = cat_counts.get(label, 0) + 1

    sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1])
    fig_bar = go.Figure(
        go.Bar(
            y=[c[0] for c in sorted_cats],
            x=[c[1] for c in sorted_cats],
            orientation="h",
            marker_color=COLORS["accent"],
            hovertemplate="<b>%{y}</b>: %{x} signals<extra></extra>",
        )
    )
    fig_bar.update_layout(
        **PLOTLY_LAYOUT,
        title="Signals by Category",
        height=max(250, len(sorted_cats) * 40 + 80),
    )
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("No signals detected in this time window.")

# ── Price Change Distribution ────────────────────────────────────────────────
st.subheader("Price Change Distribution")

if signals:
    changes = [s.price_change_pct for s in signals]
    fig_hist = go.Figure(
        go.Histogram(
            x=changes,
            nbinsx=30,
            marker_color=COLORS["accent"],
            marker_line_color=COLORS["bg"],
            marker_line_width=1,
            hovertemplate="Change: %{x:.2f}%<br>Count: %{y}<extra></extra>",
        )
    )
    fig_hist.update_layout(
        **PLOTLY_LAYOUT,
        title="Distribution of Price Moves (%)",
        height=350,
        xaxis_title="Price Change %",
        yaxis_title="Count",
    )
    st.plotly_chart(fig_hist, use_container_width=True)
    st.caption(
        "Where most market moves cluster -- larger moves are rarer but more significant"
    )
else:
    st.info("No price change data to display.")

st.divider()

# ── Signal Feed ──────────────────────────────────────────────────────────────
st.subheader("Signal Feed")

if signals:
    for s in signals:
        now = datetime.utcnow()
        det = s.detected_at.replace(tzinfo=None) if s.detected_at.tzinfo else s.detected_at
        delta = now - det
        total_secs = delta.total_seconds()
        if total_secs < 3600:
            ago = f"{int(total_secs // 60)}m ago"
        elif total_secs < 86400:
            ago = f"{int(total_secs // 3600)}h ago"
        else:
            ago = f"{int(total_secs // 86400)}d ago"

        short_q = s.market_question[:60] + ("..." if len(s.market_question) > 60 else "")
        sign = "+" if s.price_change_pct >= 0 else ""
        title = f"{short_q} | {sign}{s.price_change_pct:.1f}% | {s.category or 'N/A'} | {ago}"

        with st.expander(title):
            st.write(f"**Question:** {s.market_question}")
            st.write(f"**Current Price:** {s.current_price:.4f}")
            st.write(f"**Price Change:** {sign}{s.price_change_pct:.2f}%")
            st.write(f"**Timeframe:** {s.timeframe_minutes} min")
            st.write(f"**Category:** {s.category or 'N/A'}")
            st.write(f"**Detected:** {s.detected_at.strftime('%Y-%m-%d %H:%M UTC')}")

            analysis = analysis_by_signal.get(s.id)
            if analysis:
                st.divider()
                st.write("**AI Analysis**")
                conv = analysis.conviction_score
                if conv >= 0.7:
                    badge = f'<span style="color:{COLORS["up"]};font-weight:700">Conviction: {conv:.0%}</span>'
                elif conv >= 0.4:
                    badge = f'<span style="color:#ffab40;font-weight:700">Conviction: {conv:.0%}</span>'
                else:
                    badge = f'<span style="color:{COLORS["down"]};font-weight:700">Conviction: {conv:.0%}</span>'
                st.markdown(badge, unsafe_allow_html=True)
                st.write(f"**Direction:** {analysis.suggested_direction.value.upper()}")
                st.write(f"**Reasoning:** {analysis.reasoning}")
                if analysis.risk_notes:
                    st.write(f"**Risk Notes:** {analysis.risk_notes}")
else:
    st.info("No signals to display. The agent will populate this feed as it detects market movements.")
