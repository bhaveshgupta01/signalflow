import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from db import init_db, get_stats, get_all_positions, get_recent_analyses, get_recent_decisions
from styles.theme import COLORS, apply_theme, plotly_layout

init_db()
apply_theme()

PLOTLY_LAYOUT = plotly_layout()

# ── Header ───────────────────────────────────────────────────────────────────
st.header("Agent Performance")
st.caption(
    "How smart is the agent? This page analyzes whether higher conviction predictions "
    "actually lead to better returns, and tracks the agent's decision-making over time."
)

# ── Load data ────────────────────────────────────────────────────────────────
stats = get_stats()
positions = get_all_positions(limit=200)
analyses = get_recent_analyses(limit=200)
decisions = get_recent_decisions(limit=100)

closed_positions = [p for p in positions if p.status.value != "open"]
avg_conviction = (
    sum(a.conviction_score for a in analyses) / len(analyses) if analyses else 0
)

# ── Summary Metrics ──────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
pnl = stats["total_pnl"]
pnl_delta_color = "normal" if pnl >= 0 else "inverse"
c1.metric("Total PnL", f"${pnl:+,.2f}", delta=f"{'profit' if pnl >= 0 else 'loss'}", delta_color=pnl_delta_color)
c2.metric("Win Rate", f"{stats['win_rate']:.1f}%", delta=f"{stats['wins']}/{stats['closed_trades']} wins")
c3.metric("Total Analyses", len(analyses))
c4.metric("Avg Conviction", f"{avg_conviction:.0%}")

st.divider()

# ── Conviction vs PnL Scatter ────────────────────────────────────────────────
st.subheader("Conviction vs PnL")

analysis_map = {a.id: a for a in analyses}

if closed_positions:
    scatter_data = []
    for p in closed_positions:
        a = analysis_map.get(p.analysis_id)
        if a:
            scatter_data.append({
                "conviction": a.conviction_score,
                "pnl": p.pnl,
                "direction": p.direction.value,
                "asset": p.asset,
            })

    if scatter_data:
        df_scatter = pd.DataFrame(scatter_data)
        longs = df_scatter[df_scatter["direction"] == "long"]
        shorts = df_scatter[df_scatter["direction"] == "short"]

        fig_scatter = go.Figure()
        if not longs.empty:
            fig_scatter.add_trace(go.Scatter(
                x=longs["conviction"], y=longs["pnl"],
                mode="markers", name="Long",
                marker=dict(color=COLORS["up"], size=10, opacity=0.8),
                text=longs["asset"],
                hovertemplate="Asset: %{text}<br>Conviction: %{x:.0%}<br>PnL: $%{y:+.2f}<extra></extra>",
            ))
        if not shorts.empty:
            fig_scatter.add_trace(go.Scatter(
                x=shorts["conviction"], y=shorts["pnl"],
                mode="markers", name="Short",
                marker=dict(color=COLORS["down"], size=10, opacity=0.8),
                text=shorts["asset"],
                hovertemplate="Asset: %{text}<br>Conviction: %{x:.0%}<br>PnL: $%{y:+.2f}<extra></extra>",
            ))

        fig_scatter.add_hline(y=0, line_dash="dash", line_color=COLORS["muted"], opacity=0.5)
        fig_scatter.update_layout(
            **PLOTLY_LAYOUT,
            title="Conviction vs Trade PnL",
            height=400,
            xaxis_title="Conviction Score",
            yaxis_title="PnL ($)",
        )
        fig_scatter.update_xaxes(tickformat=".0%")
        st.plotly_chart(fig_scatter, use_container_width=True)
        st.caption(
            "Each dot is a closed trade. If high-conviction trades cluster in the "
            "profit zone (top-right), the agent's analysis is working."
        )
    else:
        st.info("No closed trades with matching analyses yet.")
else:
    st.info("No closed positions to plot. Data will appear after the agent closes trades.")

st.divider()

# ── Asset Allocation + Agent Activity ────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Asset Allocation")
    if positions:
        asset_totals: dict[str, float] = {}
        for p in positions:
            asset_totals[p.asset] = asset_totals.get(p.asset, 0) + p.size_usd

        fig_pie = go.Figure(go.Pie(
            labels=list(asset_totals.keys()),
            values=list(asset_totals.values()),
            hole=0.45,
            marker=dict(colors=[
                COLORS["accent"], COLORS["up"], COLORS["down"],
                "#ffab40", "#29b6f6", "#ab47bc",
            ]),
            textinfo="label+percent",
            textfont=dict(color=COLORS["text"]),
        ))
        fig_pie.update_layout(
            **PLOTLY_LAYOUT,
            title="Allocation by Asset",
            height=350,
            showlegend=False,
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No positions to display.")

with col_right:
    st.subheader("Agent Activity")
    if decisions:
        dec_df = pd.DataFrame([{
            "cycle": d.cycle_id[:8],
            "signals": d.signals_detected,
            "trades": d.trades_executed,
            "timestamp": d.timestamp,
        } for d in decisions[:20]])

        fig_act = go.Figure()
        fig_act.add_trace(go.Bar(
            x=dec_df["cycle"], y=dec_df["signals"],
            name="Signals", marker_color=COLORS["accent"],
        ))
        fig_act.add_trace(go.Bar(
            x=dec_df["cycle"], y=dec_df["trades"],
            name="Trades", marker_color=COLORS["up"],
        ))
        fig_act.update_layout(
            **PLOTLY_LAYOUT,
            title="Signals & Trades per Cycle",
            barmode="group",
            height=350,
            xaxis_title="Cycle",
            yaxis_title="Count",
        )
        fig_act.update_xaxes(tickangle=-45)
        st.plotly_chart(fig_act, use_container_width=True)
    else:
        st.info("No agent decision cycles recorded yet.")

st.divider()

# ── Decision Log ─────────────────────────────────────────────────────────────
st.subheader("Decision Log")

if analyses:
    for a in analyses:
        conv = a.conviction_score
        if conv >= 0.7:
            badge = f'<span style="color:{COLORS["up"]};font-weight:700">{conv:.0%}</span>'
        elif conv >= 0.4:
            badge = f'<span style="color:#ffab40;font-weight:700">{conv:.0%}</span>'
        else:
            badge = f'<span style="color:{COLORS["down"]};font-weight:700">{conv:.0%}</span>'

        direction_label = "LONG" if a.suggested_direction.value == "long" else "SHORT"
        title = (
            f"{a.suggested_asset} | {direction_label} | "
            f"Conviction {conv:.0%} | {a.created_at.strftime('%H:%M UTC')}"
        )

        with st.expander(title):
            st.markdown(f"**Conviction:** {badge}", unsafe_allow_html=True)
            st.write(f"**Direction:** {a.suggested_direction.value.upper()}")
            st.write(f"**Asset:** {a.suggested_asset}")
            st.write(f"**Suggested Size:** ${a.suggested_size_usd:,.2f}")
            st.write(f"**Reasoning:** {a.reasoning}")
            if a.risk_notes:
                st.write(f"**Risk Notes:** {a.risk_notes}")
            st.write(f"**Created:** {a.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
else:
    st.info("No analyses recorded yet. The agent will populate this log as it processes signals.")
