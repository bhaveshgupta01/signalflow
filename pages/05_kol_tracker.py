import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from db import init_db, get_all_kol_signals, get_recent_signals
from styles.theme import COLORS, apply_theme, plotly_layout

init_db()
apply_theme()

PLOTLY_LAYOUT = plotly_layout()

# ── Header ───────────────────────────────────────────────────────────────────
st.header("Whale Intelligence")
st.caption(
    "Monitors key opinion leader (KOL) wallets for large trades. When a whale buys "
    "or sells, the agent takes notice -- if their trade aligns with a prediction "
    "market signal, the trading conviction gets a 15% boost."
)

# ── Load data ────────────────────────────────────────────────────────────────
kol_signals = get_all_kol_signals(limit=200)

if not kol_signals:
    st.info(
        "No KOL whale signals detected yet. This page tracks large trades from "
        "key opinion leader wallets. When a whale makes a significant move "
        "(>$10,000), the agent logs it here and checks whether it aligns with "
        "Polymarket prediction signals. Aligned signals receive a 15% conviction boost."
    )
    st.stop()

# ── Summary Metrics ──────────────────────────────────────────────────────────
unique_whales = len({k.kol_name for k in kol_signals})
total_volume = sum(k.trade_size_usd for k in kol_signals)

asset_counts: dict[str, int] = {}
for k in kol_signals:
    asset_counts[k.asset] = asset_counts.get(k.asset, 0) + 1
most_active_asset = max(asset_counts, key=asset_counts.get) if asset_counts else "N/A"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total KOL Signals", len(kol_signals))
c2.metric("Unique Whales", unique_whales)
c3.metric("Most Active Asset", most_active_asset)
c4.metric("Total Volume Tracked", f"${total_volume:,.0f}")

st.divider()

# ── Volume by Asset + Activity Timeline ──────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Volume by Asset")
    asset_vol: dict[str, float] = {}
    for k in kol_signals:
        asset_vol[k.asset] = asset_vol.get(k.asset, 0) + k.trade_size_usd
    sorted_assets = sorted(asset_vol.items(), key=lambda x: x[1])

    fig_vol = go.Figure(go.Bar(
        y=[a[0] for a in sorted_assets],
        x=[a[1] for a in sorted_assets],
        orientation="h",
        marker_color=COLORS["accent"],
        text=[f"${v:,.0f}" for _, v in sorted_assets],
        textposition="auto",
        hovertemplate="<b>%{y}</b>: $%{x:,.0f}<extra></extra>",
    ))
    fig_vol.update_layout(
        **PLOTLY_LAYOUT,
        title="KOL Volume by Asset ($)",
        height=350,
        xaxis_title="Volume ($)",
    )
    st.plotly_chart(fig_vol, use_container_width=True)

with col_right:
    st.subheader("Activity Timeline")
    longs = [k for k in kol_signals if k.direction.value == "long"]
    shorts = [k for k in kol_signals if k.direction.value == "short"]

    fig_timeline = go.Figure()
    if longs:
        fig_timeline.add_trace(go.Scatter(
            x=[k.detected_at for k in longs],
            y=[k.trade_size_usd for k in longs],
            mode="markers", name="Long",
            marker=dict(color=COLORS["up"], size=10, opacity=0.8),
            text=[k.kol_name for k in longs],
            hovertemplate="%{text}<br>Size: $%{y:,.0f}<br>Time: %{x}<extra></extra>",
        ))
    if shorts:
        fig_timeline.add_trace(go.Scatter(
            x=[k.detected_at for k in shorts],
            y=[k.trade_size_usd for k in shorts],
            mode="markers", name="Short",
            marker=dict(color=COLORS["down"], size=10, opacity=0.8),
            text=[k.kol_name for k in shorts],
            hovertemplate="%{text}<br>Size: $%{y:,.0f}<br>Time: %{x}<extra></extra>",
        ))
    fig_timeline.update_layout(
        **PLOTLY_LAYOUT,
        title="KOL Trades Over Time",
        height=350,
        xaxis_title="Time",
        yaxis_title="Trade Size ($)",
    )
    st.plotly_chart(fig_timeline, use_container_width=True)

st.divider()

# ── Whale Activity Feed ──────────────────────────────────────────────────────
st.subheader("Whale Activity Feed")

for k in kol_signals:
    arrow = "LONG" if k.direction.value == "long" else "SHORT"
    dir_symbol = "^" if k.direction.value == "long" else "v"
    title = f"{k.kol_name} | {dir_symbol} {arrow} {k.asset} | ${k.trade_size_usd:,.0f}"

    with st.expander(title):
        truncated_wallet = (
            k.wallet_address[:6] + "..." + k.wallet_address[-4:]
            if len(k.wallet_address) > 12
            else k.wallet_address
        )
        st.write(f"**Wallet:** `{truncated_wallet}`")
        st.write(f"**Direction:** {k.direction.value.upper()}")
        st.write(f"**Asset:** {k.asset}")
        st.write(f"**Trade Size:** ${k.trade_size_usd:,.2f}")
        st.write(f"**Detected:** {k.detected_at.strftime('%Y-%m-%d %H:%M UTC')}")

st.divider()

# ── Signal Correlation Table ─────────────────────────────────────────────────
st.subheader("Signal Correlation Table")

market_signals = get_recent_signals(minutes=60 * 24 * 365)

correlation_rows = []
for k in kol_signals:
    kol_asset_upper = k.asset.upper()
    matching = [
        s for s in market_signals
        if kol_asset_upper in s.market_question.upper()
        or kol_asset_upper in s.category.upper()
    ]
    has_match = len(matching) > 0

    aligned = False
    if has_match:
        for s in matching:
            poly_bullish = s.price_change_pct > 0
            kol_bullish = k.direction.value == "long"
            if poly_bullish == kol_bullish:
                aligned = True
                break

    correlation_rows.append({
        "KOL": k.kol_name,
        "Asset": k.asset,
        "Direction": k.direction.value.upper(),
        "Polymarket Match?": "Yes" if has_match else "No",
        "Aligned?": "Yes" if aligned else ("N/A" if not has_match else "No"),
    })

if correlation_rows:
    df_corr = pd.DataFrame(correlation_rows)
    st.dataframe(df_corr, use_container_width=True, hide_index=True)
else:
    st.info("No correlation data available yet.")

st.caption(
    "The agent automatically boosts conviction by 15% when a KOL trade aligns "
    "with a Polymarket signal on the same asset"
)
