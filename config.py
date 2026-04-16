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

# ── Risk Management (v2: fixed-fractional) ──────────────────────────────────
MAX_SINGLE_POSITION_PCT = 0.30   # hard cap: notional per position can't exceed 30% of wallet
DEFAULT_STOP_LOSS_PCT = 0.025    # 2.5% stop fallback when ATR unavailable
DEFAULT_TAKE_PROFIT_PCT = 0.075  # 7.5% TP fallback (1:3 R:R)
MAX_POSITION_AGE_HOURS = 12      # hard mechanical max (was 6)
MIN_FLIP_INTERVAL_MINUTES = 10

# v2 sizing: every trade risks the same fraction of the wallet
RISK_PCT_PER_TRADE = 0.015       # 1.5% of wallet at risk per trade

# ── ATR-Based Dynamic Stops (v2: tighter SL, fatter TP) ─────────────────────
ATR_PERIOD = 14
ATR_TIMEFRAME = "1h"
ATR_SL_MULTIPLIER = 1.0          # stop = entry ± 1.0 × ATR (was 1.5)
ATR_TP_MULTIPLIER = 3.0          # tp   = entry ± 3.0 × ATR  (1:3 R:R)
CHANDELIER_ATR_MULT = 2.0        # trail stop = highest_high − 2 × ATR
CHANDELIER_ACTIVATION_ATR = 1.5  # only start trailing once price has moved 1.5 × ATR in our favour

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
CONVICTION_THRESHOLD = 0.45       # legacy floor; v2 also uses per-asset score thresholds below

# ── v2 Multi-Source Scoring ─────────────────────────────────────────────────
# A trade fires when |total_score| >= threshold for that asset.
# Scores: funding ±1.0, polymarket ±0.6, kol ±0.6, trend ±0.4
SCORE_THRESHOLD_MAJORS = 1.1   # BTC, ETH — high bar (v2.1: was 1.8, unreachable without active funding/KOL)
SCORE_THRESHOLD_ALTS = 0.65    # everything else (v2.1.1: was 0.8; lowered after SOL +22% + uptrend scored 0.68 and got rejected)
SCORE_WEIGHT_FUNDING = 1.0
SCORE_WEIGHT_POLYMARKET = 0.6
SCORE_WEIGHT_KOL = 0.6
SCORE_WEIGHT_TREND = 0.4

# Funding extreme = standalone trigger and high-weight confirming signal
FUNDING_EXTREME_THRESHOLD = 0.00025  # |rate| > 0.025% per 8h ⇒ extreme

# Tradable asset whitelist — anything outside this is rejected at execute time
TRADABLE_ASSETS = {
    "BTC", "ETH", "SOL", "DOGE", "ARB", "AVAX",
    "LINK", "SUI", "INJ", "OP", "APT",
}
ASSET_MAJORS = {"BTC", "ETH"}

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
