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
MIN_SIGNAL_PRICE_CHANGE = 0.05  # 5% move = worth investigating (raised from 3% to filter noise)
SIGNAL_DEDUP_MINUTES = 15       # 15-min dedup — avoid re-triggering on the same market too fast
MARKET_CATEGORIES = ["crypto", "bitcoin", "ethereum", "defi", "regulation", "SEC", "ETF", "solana"]

# ── Risk Management (disciplined — protect the wallet) ───────────────────────
MAX_SINGLE_POSITION_PCT = 0.30   # max 30% of balance on one trade (was 50%)
DEFAULT_STOP_LOSS_PCT = 0.03     # 3% stop-loss (tighter = cut losers faster)
DEFAULT_TAKE_PROFIT_PCT = 0.08   # 8% take-profit (realistic target for 4h window)
MAX_POSITION_AGE_HOURS = 4       # auto-close any position older than 4 hours

# ── Agent ────────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"
CONVICTION_THRESHOLD = 0.72       # higher bar = fewer but better trades (raised from 0.55)
TRADE_COOLDOWN_MINUTES = 10       # minimum wait between opening new positions

# ── Trigger Intervals (slower = more deliberate, less noise) ─────────────────
POLYMARKET_TRIGGER_INTERVAL = 90     # scan every 90s (was 45s)
KOL_TRIGGER_INTERVAL = 120          # check whales every 2 min (was 60s)
FUNDING_TRIGGER_INTERVAL = 180      # funding rates every 3 min (was 90s)
TOKEN_DISCOVERY_INTERVAL = 240      # trending tokens every 4 min (was 2 min)
CROSS_CHAIN_INTERVAL = 300          # cross-chain arb every 5 min (was 3 min)
PORTFOLIO_TRIGGER_INTERVAL = 300    # wallet sync every 5 min

# ── Funding / Cross-Chain Thresholds ─────────────────────────────────────────
FUNDING_RATE_THRESHOLD = 0.0001     # 0.01% deviation
CROSS_CHAIN_THRESHOLD = 0.003       # 0.3% price diff (more aggressive)

# ── KOL Tracking ─────────────────────────────────────────────────────────────
KOL_POLL_ENABLED = True
KOL_MIN_TRADE_USD = 500         # only track meaningful trades >$500 (was $100)
KOL_SIGNAL_BOOST = 0.10         # +10% conviction when KOL aligns (was 15%, toned down)
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
