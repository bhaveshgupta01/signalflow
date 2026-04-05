"""SignalFlow shared dark theme — colors, CSS injection, and Plotly defaults."""

import streamlit as st

COLORS = {
    "up": "#00e676",
    "down": "#ff5252",
    "accent": "#6c63ff",
    "bg": "#0e1117",
    "card": "#1a1f2e",
    "border": "rgba(255,255,255,0.08)",
    "text": "#e0e0e0",
    "muted": "#9e9e9e",
}


def apply_theme() -> None:
    """Inject global CSS for the SignalFlow dark theme."""
    st.markdown(
        f"""
        <style>
        /* ── General layout ─────────────────────────────────────────── */
        .block-container {{
            padding-top: 1.2rem;
            padding-bottom: 1rem;
            max-width: 1320px;
        }}

        /* ── Metric cards ───────────────────────────────────────────── */
        div[data-testid="stMetric"] {{
            background: linear-gradient(145deg, {COLORS["card"]}, rgba(14,17,23,0.9));
            border: 1px solid {COLORS["border"]};
            border-radius: 14px;
            padding: 18px 22px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        div[data-testid="stMetric"]:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 28px rgba(0,0,0,0.35);
        }}
        div[data-testid="stMetric"] label {{
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            opacity: 0.6;
        }}
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
            font-size: 1.5rem;
            font-weight: 700;
        }}

        /* ── Card containers ────────────────────────────────────────── */
        .sf-card {{
            background: {COLORS["card"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 12px;
            padding: 14px 18px;
            margin-bottom: 10px;
        }}

        /* ── Signal card ────────────────────────────────────────────── */
        .sf-signal-card {{
            background: {COLORS["card"]};
            border-left: 3px solid {COLORS["accent"]};
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
            transition: background 0.15s ease;
        }}
        .sf-signal-card:hover {{
            background: rgba(108,99,255,0.08);
        }}
        .sf-signal-card .question {{
            font-weight: 600;
            font-size: 0.9rem;
            color: {COLORS["text"]};
            margin-bottom: 4px;
            line-height: 1.35;
        }}
        .sf-signal-card .meta {{
            font-size: 0.76rem;
            color: {COLORS["muted"]};
        }}

        /* ── Section headers ────────────────────────────────────────── */
        .sf-section {{
            font-size: 1rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: {COLORS["text"]};
            margin-bottom: 0.75rem;
            padding-bottom: 0.4rem;
            border-bottom: 2px solid rgba(108,99,255,0.3);
        }}

        /* ── PnL coloring ───────────────────────────────────────────── */
        .pnl-pos {{ color: {COLORS["up"]}; font-weight: 700; }}
        .pnl-neg {{ color: {COLORS["down"]}; font-weight: 700; }}
        .pnl-zero {{ color: {COLORS["muted"]}; font-weight: 600; }}

        /* ── Conviction badges ──────────────────────────────────────── */
        .conviction-high {{ color: {COLORS["up"]}; font-weight: 700; }}
        .conviction-mid  {{ color: #ffab40; font-weight: 700; }}
        .conviction-low  {{ color: {COLORS["down"]}; font-weight: 700; }}

        /* ── Status indicators ──────────────────────────────────────── */
        .sf-status-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 6px;
            vertical-align: middle;
        }}
        .sf-status-dot.live {{
            background: {COLORS["up"]};
            box-shadow: 0 0 8px {COLORS["up"]};
            animation: sf-pulse 2s ease-in-out infinite;
        }}
        @keyframes sf-pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.4; }}
        }}

        /* ── KOL alert row ──────────────────────────────────────────── */
        .sf-kol-row {{
            background: {COLORS["card"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 8px;
            padding: 10px 14px;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 0.85rem;
        }}
        .sf-kol-row .kol-icon {{
            font-size: 1.1rem;
            flex-shrink: 0;
        }}

        /* ── Styled tables ──────────────────────────────────────────── */
        div[data-testid="stDataFrame"] table {{
            border-collapse: collapse;
        }}
        div[data-testid="stDataFrame"] th {{
            background: {COLORS["card"]} !important;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: {COLORS["muted"]} !important;
            border-bottom: 1px solid {COLORS["border"]} !important;
        }}
        div[data-testid="stDataFrame"] td {{
            font-size: 0.85rem;
            border-bottom: 1px solid {COLORS["border"]} !important;
        }}

        /* ── Progress bars ──────────────────────────────────────────── */
        div[data-testid="stProgress"] > div > div {{
            background: {COLORS["accent"]} !important;
            border-radius: 6px;
        }}

        /* ── Expander styling ───────────────────────────────────────── */
        div[data-testid="stExpander"] {{
            background: {COLORS["card"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 10px;
            margin-bottom: 6px;
        }}
        div[data-testid="stExpander"] summary {{
            font-size: 0.88rem;
            font-weight: 600;
        }}

        /* ── Typography ─────────────────────────────────────────────── */
        html, body, [class*="css"] {{
            font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI",
                         Roboto, Helvetica, Arial, sans-serif;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def plotly_layout() -> dict:
    """Return Plotly layout defaults matching the SignalFlow dark theme."""
    return {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {
            "family": "Inter, -apple-system, sans-serif",
            "color": COLORS["text"],
            "size": 12,
        },
        "xaxis": {
            "gridcolor": "rgba(255,255,255,0.05)",
            "zerolinecolor": "rgba(255,255,255,0.08)",
            "tickfont": {"color": COLORS["muted"]},
        },
        "yaxis": {
            "gridcolor": "rgba(255,255,255,0.05)",
            "zerolinecolor": "rgba(255,255,255,0.08)",
            "tickfont": {"color": COLORS["muted"]},
        },
        "colorway": [
            COLORS["accent"],
            COLORS["up"],
            COLORS["down"],
            "#ffab40",
            "#29b6f6",
            "#ab47bc",
        ],
        "margin": {"l": 40, "r": 20, "t": 40, "b": 40},
        "legend": {
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"color": COLORS["muted"]},
        },
        "hoverlabel": {
            "bgcolor": COLORS["card"],
            "font_color": COLORS["text"],
            "bordercolor": COLORS["border"],
        },
    }
