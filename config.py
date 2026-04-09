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
USE_VERTEX = os.getenv("USE_VERTEX", "false").lower() == "true"

# ── Signal Detection ─────────────────────────────────────────────────────────
MIN_SIGNAL_PRICE_CHANGE = 0.04  # 4% move — lowered to catch more actionable signals
SIGNAL_DEDUP_MINUTES = 8        # 8-min dedup — faster reaction to changing markets
MARKET_CATEGORIES = ["crypto", "bitcoin", "ethereum", "defi", "regulation", "SEC", "ETF", "solana"]

# ── Risk Management ──────────────────────────────────────────────────────────
MAX_SINGLE_POSITION_PCT = 0.30   # max 30% of balance on one trade (was 25%)
DEFAULT_STOP_LOSS_PCT = 0.05     # 5% stop-loss (fallback when ATR unavailable)
DEFAULT_TAKE_PROFIT_PCT = 0.10   # 10% take-profit (fallback when ATR unavailable)
MAX_POSITION_AGE_HOURS = 6       # auto-close any position older than 6 hours (was 4)
MIN_FLIP_INTERVAL_MINUTES = 10   # allow faster direction changes (was 30)

# ── ATR-Based Dynamic Stops ─────────────────────────────────────────────────
ATR_PERIOD = 14                  # 14-period ATR (industry standard)
ATR_TIMEFRAME = "1h"             # 1-hour candles for ATR calculation
ATR_SL_MULTIPLIER = 1.5          # stop-loss = entry ± ATR * 1.5
ATR_TP_MULTIPLIER = 3.0          # take-profit = entry ± ATR * 3.0 (2:1 R:R)

# ── Portfolio Drawdown Circuit Breaker ──────────────────────────────────────
DRAWDOWN_WARN_PCT = 0.15         # 15% drawdown: halve new position sizes
DRAWDOWN_HALT_PCT = 0.30         # 30% drawdown: stop all new trades
DRAWDOWN_COOLDOWN_HOURS = 4      # hours to wait after halt before resuming

# ── Execution Quality ───────────────────────────────────────────────────────
MIN_ORDERBOOK_DEPTH_USD = 500    # min liquidity at top-3 levels to enter
MAX_SLIPPAGE_PCT = 0.05          # 5% max slippage — paper trading, orderbook API often returns inflated estimates

# ── Trend Regime Detection ──────────────────────────────────────────────────
TREND_EMA_FAST = 8               # fast EMA period (hours)
TREND_EMA_SLOW = 21              # slow EMA period (hours)
TREND_BLOCK_COUNTER = False      # allow counter-trend trades (was True — blocked too many)

# ── Anti-Churn ──────────────────────────────────────────────────────────────
MIN_HOLD_MINUTES = 20            # minimum hold before AI can suggest exit (was 30)
MIN_TIME_BETWEEN_TRADES = 3      # minutes between consecutive trades on same asset (was 5)

# ── Signal Quality ──────────────────────────────────────────────────────────
SIGNAL_MIN_PROBABILITY = 0.08    # slightly wider band to catch more signals
SIGNAL_MAX_PROBABILITY = 0.92    # slightly wider band
SIGNAL_REJECT_TARGET_RATIO = 0.30

# ── Agent ────────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash-lite"
CONVICTION_THRESHOLD = 0.45       # lowered from 0.68 — the new prompt calibrates conviction properly

# ── Trigger Intervals (fast — event-driven, scan aggressively) ───────────────
POLYMARKET_TRIGGER_INTERVAL = 40     # scan every 40s (was 45)
KOL_TRIGGER_INTERVAL = 50           # check whales every 50s (was 60)
FUNDING_TRIGGER_INTERVAL = 75       # funding rates every 75s (was 90)
TOKEN_DISCOVERY_INTERVAL = 100      # trending tokens every 100s (was 120)
CROSS_CHAIN_INTERVAL = 150          # cross-chain arb every 2.5 min (was 180)
PORTFOLIO_TRIGGER_INTERVAL = 240    # wallet sync every 4 min (was 300)

# ── Funding / Cross-Chain Thresholds ─────────────────────────────────────────
FUNDING_RATE_THRESHOLD = 0.0001     # 0.01% deviation
CROSS_CHAIN_THRESHOLD = 0.003       # 0.3% price diff

# ── KOL Tracking ─────────────────────────────────────────────────────────────
KOL_POLL_ENABLED = True
KOL_MIN_TRADE_USD = 300         # lowered from $500 to catch more whale activity
KOL_SIGNAL_BOOST = 0.15         # +15% conviction boost when KOL aligns (was 10%)
KOL_DEDUP_MINUTES = 20          # faster dedup (was 30)

# ── Boba MCP ─────────────────────────────────────────────────────────────────
BOBA_MCP_COMMAND = "npx"
BOBA_MCP_ARGS = ["-y", "@tradeboba/cli@latest"]

# ── Database ─────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("SIGNALFLOW_DB_PATH", "signalflow.db")

# ── Paper Trading ────────────────────────────────────────────────────────────
PAPER_WALLET_STARTING_BALANCE = 100.0

# ── Portfolio Limits ────────────────────────────────────────────────────────
MAX_PORTFOLIO_EXPOSURE_USD = 1000   # max total USD across all open positions
MAX_CONCURRENT_POSITIONS = 8       # raised from 5 — more assets, more diversification

# ── Dashboard ────────────────────────────────────────────────────────────────
DASHBOARD_REFRESH_SECONDS = 10
