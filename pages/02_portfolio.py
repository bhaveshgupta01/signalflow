"""Portfolio — one chart to rule them all."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

from styles.theme import COLORS, apply_theme
from db import (
    init_db, get_all_positions, get_open_positions, get_stats,
    get_wallet_history, get_recent_analyses,
    get_asset_pnl_history, get_trade_events, get_position_snapshots,
)
from models import PositionStatus

init_db()
apply_theme()

try:
    from config import PAPER_WALLET_STARTING_BALANCE
except ImportError:
    PAPER_WALLET_STARTING_BALANCE = 100.0

PLOTLY_LAYOUT = dict(
    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e0e0e0"),
    margin=dict(l=40, r=20, t=50, b=40),
)

_LOCAL_OFFSET = datetime.now(timezone.utc).astimezone().utcoffset() or timedelta(0)
def _local(dt):
    return dt + _LOCAL_OFFSET

ASSET_COLORS = {
    "BTC": "#f7931a", "ETH": "#627eea", "SOL": "#9945ff",
    "DOGE": "#c2a633", "AVAX": "#e84142", "ARB": "#28a0f0",
    "MATIC": "#8247e5", "LINK": "#2a5ada", "OP": "#ff0420",
    "PEPE": "#4ca843", "WIF": "#e8a838", "JUP": "#00b4d8",
}

# ── Data ──────────────────────────────────────────────────────────────────────

positions = get_all_positions(limit=200)
open_pos = get_open_positions()
stats = get_stats()
wallet_history = get_wallet_history(limit=5000)
analyses = get_recent_analyses(limit=200)
trade_events = get_trade_events()
analysis_map = {a.id: a for a in analyses if a.id is not None}

total_pnl = stats["total_pnl"]
current_value = PAPER_WALLET_STARTING_BALANCE + total_pnl
return_pct = (total_pnl / PAPER_WALLET_STARTING_BALANCE * 100) if PAPER_WALLET_STARTING_BALANCE else 0
closed = [p for p in positions if p.status != PositionStatus.OPEN]
wins = sum(1 for p in closed if p.pnl > 0)
win_rate = (wins / len(closed) * 100) if closed else 0

# ═══════════════════════════════════════════════════════════════════════════════
# HEADER — P&L and Win Rate LOUD
# ═══════════════════════════════════════════════════════════════════════════════

st.header("Portfolio")

pnl_color = COLORS["up"] if total_pnl >= 0 else COLORS["down"]
wr_color = COLORS["up"] if win_rate >= 50 else COLORS["down"]

st.markdown(
    f'<div style="display:flex;gap:24px;align-items:baseline;margin-bottom:8px;">'
    f'<span style="font-size:2.2rem;font-weight:800;color:{pnl_color};">'
    f'${current_value:.2f}</span>'
    f'<span style="font-size:1.3rem;font-weight:700;color:{pnl_color};">'
    f'{"+" if total_pnl>=0 else ""}${total_pnl:.2f} ({return_pct:+.1f}%)</span>'
    f'<span style="font-size:1.1rem;color:{wr_color};font-weight:700;">'
    f'{win_rate:.0f}% win rate</span>'
    f'<span style="font-size:0.85rem;color:{COLORS["muted"]};">'
    f'{wins}W / {len(closed)-wins}L / {len(open_pos)} open</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════════════
# THE ONE CHART — wallet + each investment's journey
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()

range_col1, range_col2 = st.columns([4, 1])
with range_col1:
    st.subheader("Investment Performance")
with range_col2:
    time_range = st.selectbox("Range", ["1H", "6H", "1D", "ALL"], index=3, key="rng")

range_min = {"1H": 60, "6H": 360, "1D": 1440, "ALL": 999999}
cutoff = datetime.utcnow() - timedelta(minutes=range_min[time_range])

fig = go.Figure()

# ── Total wallet balance (thick white line) ──
if wallet_history and len(wallet_history) > 1:
    filtered = sorted(
        [w for w in wallet_history if w.timestamp >= cutoff],
        key=lambda w: w.timestamp,
    )
    if len(filtered) < 2:
        filtered = sorted(wallet_history, key=lambda w: w.timestamp)

    fig.add_trace(go.Scatter(
        x=[_local(w.timestamp) for w in filtered],
        y=[w.balance for w in filtered],
        mode="lines", name="Total Wallet",
        line=dict(color="white", width=3),
        hovertemplate="<b>Wallet</b><br>%{x|%I:%M %p}<br>$%{y:.2f}<extra></extra>",
    ))

# ── Each position as its own investment line ──
# Shows: "I put $70 in BTC, here's how that $70 is moving"
# Value = margin_invested + unrealized_pnl at each snapshot
for p in positions:
    if p.id is None:
        continue
    snapshots = get_position_snapshots(position_id=p.id, minutes=range_min[time_range])
    if not snapshots:
        continue

    color = ASSET_COLORS.get(p.asset, COLORS["accent"])
    margin = p.size_usd / max(p.leverage, 1)
    arrow = "LONG" if p.direction.value == "long" else "SHORT"
    label = f"{arrow} {p.asset} ${p.size_usd:.0f}"

    # Each snapshot: margin_invested + unrealized_pnl = current value of this investment
    times = [_local(s.timestamp) for s in snapshots]
    values = [round(margin + s.unrealized_pnl, 2) for s in snapshots]

    # Add the opening point
    if p.opened_at >= cutoff:
        times.insert(0, _local(p.opened_at))
        values.insert(0, margin)

    status_tag = ""
    if p.status == PositionStatus.CLOSED:
        status_tag = f" [CLOSED PnL ${p.pnl:+.2f}]"
    elif p.status == PositionStatus.STOPPED:
        status_tag = f" [STOPPED PnL ${p.pnl:+.2f}]"

    fig.add_trace(go.Scatter(
        x=times,
        y=values,
        mode="lines",
        name=f"{label}{status_tag}",
        line=dict(
            color=color, width=2,
            dash="dot" if p.status != PositionStatus.OPEN else "solid",
        ),
        hovertemplate=(
            f"<b>{label}</b><br>"
            f"%{{x|%I:%M %p}}<br>"
            f"Value: $%{{y:.2f}}<br>"
            f"Invested: ${margin:.2f}"
            f"<extra></extra>"
        ),
    ))

# ── Buy/sell markers ──
buy_events = [e for e in trade_events if e["type"] == "open" and e["timestamp"] >= cutoff]
sell_events = [e for e in trade_events if e["type"] == "close" and e["timestamp"] >= cutoff]

if buy_events:
    fig.add_trace(go.Scatter(
        x=[_local(e["timestamp"]) for e in buy_events],
        y=[e["size_usd"] / max(e.get("leverage", 1), 1) for e in buy_events],  # margin invested
        mode="markers+text",
        name="BUY",
        marker=dict(symbol="triangle-up", size=14, color=COLORS["up"],
                    line=dict(width=1.5, color="white")),
        text=[f"BUY {e['asset']}" for e in buy_events],
        textposition="top center",
        textfont=dict(size=9, color=COLORS["up"]),
        hovertemplate="<b>BUY %{customdata[0]}</b><br>$%{customdata[1]:.0f} @ %{customdata[2]}x<extra></extra>",
        customdata=[[e["asset"], e["size_usd"], e.get("leverage", 1)] for e in buy_events],
    ))

if sell_events:
    fig.add_trace(go.Scatter(
        x=[_local(e["timestamp"]) for e in sell_events],
        y=[e["size_usd"] / max(e.get("leverage", 1), 1) for e in sell_events],
        mode="markers+text",
        name="SELL",
        marker=dict(symbol="triangle-down", size=14, color=COLORS["down"],
                    line=dict(width=1.5, color="white")),
        text=[f"SELL {e['asset']} ${e.get('pnl',0):+.2f}" for e in sell_events],
        textposition="bottom center",
        textfont=dict(size=9, color=COLORS["down"]),
        hovertemplate="<b>SELL %{customdata[0]}</b><br>PnL: $%{customdata[1]:+.2f}<extra></extra>",
        customdata=[[e["asset"], e.get("pnl", 0)] for e in sell_events],
    ))

# ── Reference line ──
fig.add_hline(y=PAPER_WALLET_STARTING_BALANCE, line_dash="dash",
              line_color=COLORS["muted"], opacity=0.4,
              annotation_text=f"Start ${PAPER_WALLET_STARTING_BALANCE:.0f}")

fig.update_layout(
    **PLOTLY_LAYOUT, height=500, showlegend=True,
    xaxis=dict(tickformat="%I:%M %p\n%b %d"),
    yaxis=dict(title="Value ($)", tickprefix="$"),
    legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
)

if not wallet_history or len(wallet_history) < 2:
    st.info("Chart will appear after the agent runs a few cycles.")
else:
    st.plotly_chart(fig, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVE POSITIONS
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader(f"Open Positions ({len(open_pos)})")

if open_pos:
    for p in open_pos:
        margin = p.size_usd / max(p.leverage, 1)
        age_h = (datetime.utcnow() - p.opened_at).total_seconds() / 3600
        pnl_color_str = "normal" if p.pnl >= 0 else "inverse"
        arrow = "^" if p.direction.value == "long" else "v"

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.metric(
                label=f"{arrow} {p.direction.value.upper()} {p.asset} ({p.leverage}x) -- {age_h:.1f}h",
                value=f"${margin:.1f} invested -> ${margin + p.pnl:.2f} now",
                delta=f"PnL ${p.pnl:+.2f}",
                delta_color=pnl_color_str,
            )
        with col2:
            st.caption(f"Entry: ${p.entry_price:,.2f}")
            st.caption(f"SL: ${p.stop_loss:,.2f}")
        with col3:
            st.caption(f"Size: ${p.size_usd:.0f}")
            st.caption(f"TP: ${p.take_profit:,.2f}")
else:
    st.info("No open positions. Agent is looking for trades.")

# ═══════════════════════════════════════════════════════════════════════════════
# TRADE HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("Trade History")

if positions:
    for p in positions[:30]:
        a = analysis_map.get(p.analysis_id)
        arrow = "^" if p.direction.value == "long" else "v"
        margin = p.size_usd / max(p.leverage, 1)
        pnl_str = f"${p.pnl:+.2f}"

        if p.status == PositionStatus.OPEN:
            badge = "OPEN"
        elif p.status == PositionStatus.STOPPED:
            badge = "STOPPED"
        else:
            badge = "CLOSED"

        title = f"{arrow} {p.direction.value.upper()} {p.asset} | ${margin:.0f} invested | {p.leverage}x | {badge} {pnl_str}"

        with st.expander(title):
            if a:
                st.markdown(f"**Edge:** {a.reasoning[:300]}")
                if a.risk_notes:
                    st.caption(f"Risk: {a.risk_notes}")
                st.caption(f"Conviction: {a.conviction_score:.0%}")
            st.caption(
                f"Entry ${p.entry_price:,.2f} | SL ${p.stop_loss:,.2f} | TP ${p.take_profit:,.2f} | "
                f"Opened {_local(p.opened_at).strftime('%b %d %I:%M %p')}"
                + (f" | Closed {_local(p.closed_at).strftime('%b %d %I:%M %p')}" if p.closed_at else "")
            )
else:
    st.info("No trades yet.")
