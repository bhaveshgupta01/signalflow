# SignalFlow — Final Project State

**Date:** 2026-04-05
**Status:** Production-ready, deployed and trading

---

## Performance (overnight run, 12 hours)

| Metric | Value |
|--------|-------|
| Starting balance | $100.00 |
| Current balance | $105.56 |
| Total PnL | +$5.56 (+5.6%) |
| Win rate | 78% (7W / 2L) |
| Total trades | 12 |
| Avg win | +$1.26 |
| Avg loss | -$0.89 |
| Best asset | ETH (+$3.72) |

---

## What Was Built

An aggressive AI crypto trading agent that:
1. Scans Polymarket prediction markets for crypto signals every 45 seconds
2. Tracks 429 KOL whale wallets for trade signals
3. Monitors Hyperliquid funding rates for arbitrage
4. Uses Gemini 2.5 Flash to analyze each signal with 85 Boba MCP tools
5. Executes leveraged perps trades on Hyperliquid
6. Manages positions with AI-driven exit analysis, trailing stops, SL/TP
7. Displays everything on a real-time Streamlit dashboard

### Key Design Decisions

- **No artificial limits** — only constraint is wallet balance. Agent trades freely.
- **Signal interpretation** — agent understands that "Will BTC dip to $50k?" dropping = BULLISH
- **Position flipping** — if agent sees better opportunity in opposite direction, closes old and opens new
- **AI exit analysis** — Gemini evaluates positions every 30 min: "should I hold or close?"
- **Aggressive parameters** — 55% conviction threshold, 3% signal threshold, 5-min dedup
- **Dead market filter** — skips resolved markets (price < 0.02 or > 0.98) to save API calls

---

## Files Changed (from original)

| File | Changes |
|------|---------|
| config.py | Aggressive params: 55% conviction, 3% signal, 5-min dedup, 4% SL, 10% TP |
| agent.py | Signal interpretation hints, AI exit analysis, position flipping, Gemini timeout |
| risk.py | Wallet-based risk only, no artificial caps, position flip support |
| signals.py | Dead market filter (skip price < 0.02 or > 0.98) |
| kol_tracker.py | Fixed Boba format parsing: KOL names, $100 threshold, SOL mapping |
| triggers.py | Exponential backoff on all triggers |
| runner.py | Boba retry/reconnect, consecutive error handling |
| db.py | Added get_trade_events(), update_position(stop_loss=), 7 indexes |
| pages/02_portfolio.py | Unified chart: wallet + per-investment lines + buy/sell markers |
| pages/01_overview.py | Fixed "Claude" -> "Gemini" reference |
| pyproject.toml | Fixed build-backend, added plotly/gunicorn deps |

## Files Created

| File | Purpose |
|------|---------|
| Dockerfile | Multi-stage Node.js + Python |
| docker-compose.yml | 3 services: boba-proxy, agent, dashboard |
| run.sh | One-command launcher |
| .gitignore | Standard ignores |
| .dockerignore | Docker build ignores |
| PROGRESS.md | This file |

---

## Database (live)

| Table | Rows | Purpose |
|-------|------|---------|
| signals | 4,447 | Polymarket price movements |
| analyses | 1,605 | Gemini conviction scores |
| positions | 12 | All trades with PnL |
| position_snapshots | 6,751 | Per-position price tracking |
| wallet_snapshots | 2,420 | Balance over time |
| kol_signals | 234 | KOL whale trades |
| agent_decisions | 2,285 | Every agent cycle logged |

**Total: ~3,930 lines of Python across 18 files**

---

## Deployment

### Local (one command)
```bash
./run.sh
```

### Docker
```bash
docker-compose up --build -d
# Dashboard: http://localhost:8501
```

### Requirements
- Python 3.11+
- Node.js 18+ (Boba CLI)
- Google Cloud Vertex AI enabled (or Gemini API key)
- Boba agent credentials

---

## How Position Management Works

```
Every event cycle (~45-60 seconds):
  |
  |-- Fetch live price from Hyperliquid
  |-- Calculate unrealized PnL
  |-- Save snapshot for charts
  |
  |-- Price hit stop-loss (4%)? -> CLOSE immediately
  |-- Price hit take-profit (10%)? -> CLOSE immediately
  |-- Profit > 5%? -> Move SL to break-even (trailing stop)
  |
  |-- Position > 1 hour old, near 30-min mark?
  |     -> Ask Gemini: "Given current market, should I hold or close?"
  |     -> Gemini checks trend, funding, orderbook
  |     -> Returns: {"action": "close", "reason": "momentum fading"}
  |     -> If close: exit with reason logged
  |
  |-- Position > 6 hours? -> CLOSE (hard safety net)
```
