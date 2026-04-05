"""SignalFlow — Multi-page dashboard entry point."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
st.set_page_config(page_title="SignalFlow", page_icon="⚡", layout="wide")

from styles.theme import apply_theme
apply_theme()

landing = st.Page("pages/00_landing.py", title="SignalFlow", icon="⚡", default=True)
overview = st.Page("pages/01_overview.py", title="Command Center", icon="📊")
portfolio = st.Page("pages/02_portfolio.py", title="Portfolio", icon="💰")
scanner = st.Page("pages/03_signals.py", title="Market Scanner", icon="📡")
whales = st.Page("pages/05_kol_tracker.py", title="Whale Intelligence", icon="🐋")
performance = st.Page("pages/04_analytics.py", title="Agent Performance", icon="📈")

nav = st.navigation([landing, overview, portfolio, scanner, whales, performance])
nav.run()
