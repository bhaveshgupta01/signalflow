# SignalFlow — Project Handover Document

## What This Project Is

SignalFlow is an **event-driven AI trading agent** with **institutional-grade risk management** that:
1. Monitors Polymarket prediction markets for crypto-related signals
2. Tracks KOL (whale) wallet activity for trade alignment
3. Monitors Hyperliquid funding rate anomalies
4. Scans for trending tokens and cross-chain price opportunities
5. Analyzes signals using Gemini 2.5 Flash AI
6. Runs every trade through a 5-layer risk pipeline (drawdown breaker, margin, orderbook, ATR stops, fill confirmation)
7. Executes perpetual futures trades on Hyperliquid via Boba MCP
8. Manages a $100 paper trading wallet with live PnL tracking

Built to impress the Boba Agents team — demonstrates deep usage of their 85-tool MCP platform, including execution quality tools most agents never touch.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│              6 EVENT-DRIVEN TRIGGERS                  │
│  Polymarket (45s) | KOL (60s) | Funding (90s)        │
│  Token Discovery (120s) | Cross-Chain (180s)          │
│  Portfolio Sync (300s)                                │
└──────────────────────┬───────────────────────────────┘
                       ▼
              ┌─────────────────┐
              │   EVENT BUS     │
              │ asyncio.Queue   │
              └────────┬────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│                AGENT BRAIN                            │
│  1. ANALYZE: Gemini + Polymarket sentiment            │
│     (pm_get_comments, pm_get_top_holders)             │
│  2. RISK: 5-layer pipeline (see below)                │
│  3. EXECUTE: Orderbook check → market order →         │
│     fill confirmation → ATR-based SL/TP               │
│  4. MANAGE: Trailing stops, hl_close_position exits,  │
│     AI-assisted hold/close decisions                  │
│  5. SNAPSHOT: Per-position + wallet snapshots          │
└──────────────────────────────────────────────────────┘
                       ▼
              ┌─────────────────┐
              │  Streamlit UI   │
              │  6-page dash    │
              └─────────────────┘
```

---

## Risk Management — 5 Layers

This is the core differentiator. Every trade passes through all 5 layers sequentially. No LLM can override any layer.

### Layer 1: Portfolio Drawdown Circuit Breaker
- Tracks peak wallet balance in memory
- **10% drawdown from peak**: all new position sizes automatically halved
- **20% drawdown from peak**: all new trades halted for 6 hours (configurable via `DRAWDOWN_COOLDOWN_HOURS`)
- Checked in `can_open_position()` before every trade
- **Why**: Prevents catastrophic loss from correlated dumps across BTC/ETH/SOL

### Layer 2: Margin & Position Limits
- 20% cash reserve always maintained (`CASH_RESERVE_PCT`)
- Max 25% of balance per trade (`MAX_PER_TRADE_PCT`)
- Max 5 concurrent positions (`MAX_CONCURRENT_POSITIONS`)
- Max 3x leverage (`clamp_leverage()`)
- Can't hold contradictory positions (long + short same asset)
- 30-minute cooldown before flipping a position

### Layer 3: Orderbook Liquidity Gate
- **Boba tool**: `hl_get_orderbook` — fetches L2 order book depth
- Checks top-of-book liquidity on the relevant side (asks for longs, bids for shorts)
- **Rejects trade if**: depth < $500 (`MIN_ORDERBOOK_DEPTH_USD`) or estimated slippage > 0.3% (`MAX_SLIPPAGE_PCT`)
- Estimates slippage by comparing volume-weighted average price (VWAP) across top levels vs mid-price
- **Why**: Prevents entering illiquid markets where you'd get destroyed on the spread

### Layer 4: ATR-Based Dynamic Stop-Loss / Take-Profit
- **Boba tool**: `hl_get_history` — fetches OHLCV candles (1H timeframe)
- Computes ATR(14): `average of max(high-low, |high-prev_close|, |low-prev_close|)` over 14 periods
- Stop-loss = entry price ± ATR × 1.5 (`ATR_SL_MULTIPLIER`)
- Take-profit = entry price ± ATR × 3.0 (`ATR_TP_MULTIPLIER`) — maintains 2:1 reward-to-risk
- **Fallback**: If candle data unavailable, uses fixed 5% SL / 10% TP
- **Why**: BTC moves ~2-3% daily, SOL moves ~5-8%. Fixed stops ignore this — ATR stops adapt.
  A 5% stop on BTC is reasonable, but a 5% stop on SOL gets hit by normal noise.

### Layer 5: Fill Confirmation & Slippage Tracking
- **Boba tool**: `hl_get_fills` — fetches recent trade fills
- After every market order, confirms the fill actually happened
- Logs actual fill price vs expected price, calculates slippage percentage
- If actual fill price differs from expected, **recalculates SL/TP from the actual entry price**
- Warns if slippage exceeds `MAX_SLIPPAGE_PCT` threshold
- **Why**: Market orders can slip, especially on volatile assets. SL/TP should be anchored to what you actually paid, not what you expected to pay.

### Position Closing: `hl_close_position`
- All exit paths (SL, TP, planned exit, early exit, max age, flip) now use `hl_close_position`
- This is atomic — guaranteed to flatten the position with no dust remaining
- Previous approach (placing a reverse market order) could leave fragments if sizing was slightly off

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Engine | Gemini 2.5 Flash via Google Vertex AI |
| Trading MCP | Boba Agents CLI (@tradeboba/cli) — 85 tools |
| Perps Exchange | Hyperliquid (via Boba hl_* tools) |
| Prediction Markets | Polymarket (via Boba pm_* tools) |
| Event System | asyncio.Queue + 6 async trigger tasks |
| Database | SQLite with WAL mode |
| Dashboard | Streamlit + Plotly |
| Data Models | Pydantic v2 |

---

## Boba MCP Tools Used (22+)

### Direct calls in our code:
| Tool | File | Purpose |
|------|------|---------|
| pm_search_markets | signals.py | Find prediction markets by category |
| pm_get_price_history | signals.py | Detect price movements |
| pm_get_top_holders | agent.py | Whale positioning before analysis |
| pm_get_comments | agent.py | Community sentiment before analysis |
| hl_get_asset | agent.py | Get current Hyperliquid prices |
| hl_get_markets | agent.py | Market search fallback |
| hl_place_order | agent.py | Direct trade execution (market + SL + TP) |
| hl_update_leverage | agent.py | Set leverage before trades |
| hl_get_predicted_funding | triggers.py | Funding rate spike detection |
| **hl_get_history** | **risk.py** | **OHLCV candles for ATR(14) computation** |
| **hl_get_orderbook** | **risk.py** | **L2 order book depth for liquidity gate** |
| **hl_get_fills** | **risk.py** | **Fill confirmation & slippage tracking** |
| **hl_close_position** | **agent.py** | **Atomic position close (all exit paths)** |
| get_kol_swaps | kol_tracker.py | Whale trade monitoring |
| search_tokens | triggers.py | Trending token discovery |
| get_brewing_tokens | triggers.py | Launchpad token scanning |
| get_token_price | triggers.py | Cross-chain price comparison |
| get_token_info | agent.py | Token fundamentals enrichment |
| audit_token | agent.py | Security check before trades |
| get_portfolio | triggers.py | Real wallet sync |

### Available to Gemini during analysis (all 85 tools)
The agent's tool loop gives Gemini access to every Boba tool dynamically.

---

## File Structure

```
signalflow/
├── dashboard.py          # Streamlit nav router (6 pages)
├── runner.py             # Entry point — event-driven loop
├── agent.py              # Core agent: analyze, risk, execute, manage
├── event_bus.py          # Event queue + TriggerType enum
├── triggers.py           # 6 async trigger functions
├── signals.py            # Polymarket signal detection
├── kol_tracker.py        # KOL whale tracking
├── risk.py               # 5-layer risk engine (ATR, drawdown, orderbook, margin, fills)
├── mcp_client.py         # Boba MCP connection
├── config.py             # All thresholds and parameters
├── models.py             # Pydantic models (8 models)
├── db.py                 # SQLite persistence (7 tables)
├── seed_data.py          # Optional demo seeder
├── .env                  # API keys (not committed)
├── .env.example          # Key template
├── README.md             # Project documentation
├── HANDOVER.md           # This file
├── styles/
│   └── theme.py          # Shared CSS + Plotly defaults
└── pages/
    ├── 00_landing.py     # Landing page — project overview, risk layers + Boba showcase
    ├── 01_overview.py    # Command Center — pipeline + API connections
    ├── 02_portfolio.py   # Portfolio — wallet, trades, growth chart
    ├── 03_signals.py     # Market Scanner — raw signals + analysis
    ├── 04_analytics.py   # Agent Performance — conviction vs PnL
    └── 05_kol_tracker.py # Whale Intelligence — KOL tracking
```

---

## Database Schema (7 tables)

| Table | Purpose |
|-------|---------|
| signals | Polymarket price movements detected |
| analyses | Gemini's reasoning per signal (conviction, direction, asset) |
| positions | Open/closed trades with PnL |
| position_snapshots | Per-position PnL at each cycle (for per-asset charts) |
| wallet_snapshots | Aggregate wallet balance over time |
| kol_signals | KOL whale trades detected |
| agent_decisions | Summary of each agent cycle |

---

## How It Runs

### Prerequisites
1. Node.js (for npx/Boba CLI)
2. Python 3.11+
3. Google Cloud account with Vertex AI enabled (project: graphical-interface)
4. Boba agent credentials

### Startup
```bash
# Terminal 1: Boba MCP proxy (must stay running)
npx -y @tradeboba/cli@latest login --agent-id "AGENT_ID" --secret "SECRET"
npx -y @tradeboba/cli@latest proxy --port 3456

# Terminal 2: Agent
cd ~/signalflow && python3 runner.py

# Terminal 3: Dashboard
cd ~/signalflow && python3 -m streamlit run dashboard.py
```

### What happens when the agent starts:
1. Connects to Boba MCP (discovers 85 tools)
2. Creates Gemini client (Vertex AI)
3. Starts 6 trigger tasks
4. Waits for events on the event bus
5. When a trigger fires: analyze → 5-layer risk gate → execute with orderbook check → fill confirmation → manage positions → save snapshots

---

## Key Configuration (config.py)

### Signal Detection
| Parameter | Value | Purpose |
|-----------|-------|---------|
| MIN_SIGNAL_PRICE_CHANGE | 5% | Minimum Polymarket move to trigger signal |
| SIGNAL_DEDUP_MINUTES | 15 | Avoid re-triggering on same market |
| CONVICTION_THRESHOLD | 0.66 | Min AI confidence to trade |
| KOL_SIGNAL_BOOST | 0.10 | +10% conviction when KOL aligns |

### Risk Management
| Parameter | Value | Purpose |
|-----------|-------|---------|
| PAPER_WALLET_STARTING_BALANCE | $100 | Virtual capital |
| MAX_SINGLE_POSITION_PCT | 25% | Max % of wallet balance on one trade |
| MAX_CONCURRENT_POSITIONS | 5 | Max simultaneous positions |
| DEFAULT_STOP_LOSS_PCT | 5% | Fallback SL when ATR unavailable |
| DEFAULT_TAKE_PROFIT_PCT | 10% | Fallback TP when ATR unavailable |

### ATR Dynamic Stops (NEW)
| Parameter | Value | Purpose |
|-----------|-------|---------|
| ATR_PERIOD | 14 | Number of candle periods for ATR |
| ATR_TIMEFRAME | 1h | Candle interval |
| ATR_SL_MULTIPLIER | 1.5 | SL distance = ATR × 1.5 |
| ATR_TP_MULTIPLIER | 3.0 | TP distance = ATR × 3.0 |

### Drawdown Circuit Breaker (NEW)
| Parameter | Value | Purpose |
|-----------|-------|---------|
| DRAWDOWN_WARN_PCT | 10% | Halve new position sizes |
| DRAWDOWN_HALT_PCT | 20% | Stop all new trades |
| DRAWDOWN_COOLDOWN_HOURS | 6 | Hours to wait after halt |

### Execution Quality (NEW)
| Parameter | Value | Purpose |
|-----------|-------|---------|
| MIN_ORDERBOOK_DEPTH_USD | $500 | Min liquidity to enter |
| MAX_SLIPPAGE_PCT | 0.3% | Max acceptable estimated slippage |

---

## What Was Built (History)

### v1 (Day 1-2): Foundation
- Basic polling agent with APScheduler
- Claude/Anthropic SDK (later swapped to Gemini)
- Single-page Streamlit dashboard
- 5 Boba tools used

### v2 (Day 2-3): KOL Tracking + Multi-page Dashboard
- Added KOL whale tracking
- 6-page dashboard with Plotly charts
- Swapped to Gemini 2.5 Flash via Vertex AI
- Added seed data for demos

### v3 (Day 3): Event-Driven Architecture
- Replaced APScheduler with async event bus
- 3 triggers: Polymarket, KOL, Funding rate
- Added token audit before trades
- Added wallet snapshots

### v4 (Day 3-4): Deep Boba Integration
- 6 triggers: + Token Discovery, Cross-Chain, Portfolio sync
- Polymarket sentiment analysis (comments + top holders)
- Direct hl_place_order execution (not via Gemini)
- Per-position PnL snapshots for charting
- Margin enforcement in risk engine
- Streamlined to 5 pages (removed redundancy)
- 20+ Boba tools used directly

### v5 (Day 4): Landing Page + Polish
- Added landing page (00_landing.py) as default entry point
- Boba Agents MCP highlighted as the core engine with tool showcase
- Architecture, trading strategies, tech stack, risk parameters all on one page
- Dashboard now 6 pages (landing + 5 operational)

### v6 (Current): Institutional-Grade Risk Management
- **ATR-based dynamic SL/TP** via `hl_get_history` — stops scale with asset volatility
- **Portfolio drawdown circuit breaker** — halve sizes at -10%, halt at -20%
- **Orderbook liquidity gate** via `hl_get_orderbook` — reject thin/illiquid markets
- **Fill confirmation & slippage tracking** via `hl_get_fills` — verify execution, log actual costs
- **Atomic position closing** via `hl_close_position` — all exits, no dust
- 22+ Boba tools directly integrated (up from 16)
- Landing page, README, and HANDOVER updated with 5-layer risk documentation

---

## Known Issues / Future Work

### Issues
1. **Boba proxy requires terminal**: Can't run headless — needs TTY for the TUI. Deployment requires workaround.
2. **Per-asset chart data**: position_snapshots table starts empty on fresh DB. Needs a few cycles to populate.
3. **Peak balance resets on restart**: Drawdown circuit breaker tracks peak balance in-memory. Could be persisted to DB.

### Planned Improvements
1. **Volatility-normalized position sizing**: Size inversely proportional to ATR (volatile = smaller position)
2. **Correlation awareness**: Track portfolio beta to BTC, limit correlated exposure
3. **KOL wallet scoring**: Use `get_wallet_stats` to weight KOL boost by historical win rate
4. **Market regime detection**: ATR ratio + trend strength to adapt strategy (trending vs mean-reverting)
5. **DCA/TWAP execution**: Use `create_twap_order` for larger positions to reduce market impact
6. **Smart money following**: Use `search_wallets` (SNIPER/SMART_TRADER labels) + `add_wallet_to_tracker`
7. **Transaction cost model**: Track fees + funding payments alongside slippage for true net P&L
8. **Polymarket signal quality filter**: Use `pm_get_market_detail` + `pm_get_token_data` for spread/volume checks

### API Keys & Credentials
- **Gemini**: Via Google Vertex AI (project: graphical-interface, region: us-central1)
- **Boba**: Agent ID + Secret in .env (rotate after sharing)

---

## For the Next Agent/Developer

To continue this project:
1. Read this document first
2. Read README.md for the public-facing overview
3. Start with `config.py` to understand all parameters (especially the new ATR/drawdown/execution sections)
4. Read `risk.py` to understand the 5-layer risk pipeline — this is the core differentiator
5. Read `agent.py` to understand the trading pipeline and how risk layers are wired in
6. Read `triggers.py` to understand what drives the agent
7. The dashboard pages are self-contained — each imports from db.py and renders independently
8. The `styles/theme.py` controls all visual styling
9. Database is SQLite — `signalflow.db` in the project root
