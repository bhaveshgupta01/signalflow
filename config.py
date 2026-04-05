"""SignalFlow configuration — all tunable parameters in one place."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
BOBA_API_KEY = os.getenv("BOBA_API_KEY", "")

# ── Vertex AI (uses GCP billing — higher rate limits) ────────────────────────
GCP_PROJECT = os.getenv("GCP_PROJECT", "graphical-interface")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
USE_VERTEX = os.getenv("USE_VERTEX", "true").lower() == "true"

# ── Signal Detection ─────────────────────────────────────────────────────────
MIN_SIGNAL_PRICE_CHANGE = 0.03  # 3% move = worth investigating (was 5%, now more aggressive)
SIGNAL_DEDUP_MINUTES = 5        # very short dedup — re-evaluate markets every 5 min
MARKET_CATEGORIES = ["crypto", "bitcoin", "ethereum", "defi", "regulation", "SEC", "ETF", "solana"]

# ── Risk Management (minimal — let the agent trade freely) ───────────────────
# Only real constraint: don't spend more than you have
MAX_SINGLE_POSITION_PCT = 0.50   # max 50% of current balance on one trade
DEFAULT_STOP_LOSS_PCT = 0.04     # 4% stop-loss (tighter = close losers faster)
DEFAULT_TAKE_PROFIT_PCT = 0.10   # 10% take-profit (capture gains in hours not days)
MAX_POSITION_AGE_HOURS = 4       # auto-close any position older than 4 hours

# ── Agent ────────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"
CONVICTION_THRESHOLD = 0.55       # lower bar = more trades (was 0.7)

# ── Trigger Intervals (fast — act on signals quickly) ────────────────────────
POLYMARKET_TRIGGER_INTERVAL = 45     # scan every 45s
KOL_TRIGGER_INTERVAL = 60           # check whales every 60s
FUNDING_TRIGGER_INTERVAL = 90       # funding rates every 90s
TOKEN_DISCOVERY_INTERVAL = 120      # trending tokens every 2 min
CROSS_CHAIN_INTERVAL = 180          # cross-chain arb every 3 min
PORTFOLIO_TRIGGER_INTERVAL = 300    # wallet sync every 5 min

# ── Funding / Cross-Chain Thresholds ─────────────────────────────────────────
FUNDING_RATE_THRESHOLD = 0.0001     # 0.01% deviation
CROSS_CHAIN_THRESHOLD = 0.003       # 0.3% price diff (more aggressive)

# ── KOL Tracking ─────────────────────────────────────────────────────────────
KOL_POLL_ENABLED = True
KOL_MIN_TRADE_USD = 100         # Boba KOLs are Solana memecoin traders, small sizes
KOL_SIGNAL_BOOST = 0.15         # +15% conviction when KOL aligns
KOL_DEDUP_MINUTES = 30          # shorter dedup

# ── Boba MCP ─────────────────────────────────────────────────────────────────
BOBA_MCP_COMMAND = "npx"
BOBA_MCP_ARGS = ["-y", "@tradeboba/cli@latest"]

# ── Database ─────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("SIGNALFLOW_DB_PATH", "signalflow.db")

# ── Paper Trading ────────────────────────────────────────────────────────────
PAPER_WALLET_STARTING_BALANCE = 100.0

# ── Portfolio Limits ────────────────────────────────────────────────────────
MAX_PORTFOLIO_EXPOSURE_USD = 1000   # max total USD across all open positions
MAX_CONCURRENT_POSITIONS = 5       # max number of positions open at once

# ── Dashboard ────────────────────────────────────────────────────────────────
DASHBOARD_REFRESH_SECONDS = 10
