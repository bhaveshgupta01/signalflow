# SignalFlow — Project Handover Document

## What This Project Is

SignalFlow is an **event-driven AI trading agent** that:
1. Monitors Polymarket prediction markets for crypto-related signals
2. Tracks KOL (whale) wallet activity for trade alignment
3. Monitors Hyperliquid funding rate anomalies
4. Scans for trending tokens and cross-chain price opportunities
5. Analyzes signals using Gemini 2.5 Flash AI
6. Executes perpetual futures trades on Hyperliquid via Boba MCP
7. Manages a $100 paper trading wallet with live PnL tracking

Built to impress the Boba Agents team — demonstrates deep usage of their 85-tool MCP platform.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│              6 EVENT-DRIVEN TRIGGERS                  │
│  Polymarket (60s) | KOL (90s) | Funding (120s)       │
│  Token Discovery (180s) | Cross-Chain (300s)          │
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
│  2. RISK: Hard limits + margin check                  │
│  3. EXECUTE: Direct hl_place_order + SL/TP            │
│  4. MANAGE: Live PnL updates, auto-close at SL/TP    │
│  5. SNAPSHOT: Per-position + wallet snapshots          │
└──────────────────────────────────────────────────────┘
                       ▼
              ┌─────────────────┐
              │  Streamlit UI   │
              │  5-page dash    │
              └─────────────────┘
```

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

## Boba MCP Tools Used (20+)

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
├── dashboard.py          # Streamlit nav router (5 pages)
├── runner.py             # Entry point — event-driven loop
├── agent.py              # Core agent: analyze, risk, execute, manage
├── event_bus.py          # Event queue + TriggerType enum
├── triggers.py           # 6 async trigger functions
├── signals.py            # Polymarket signal detection
├── kol_tracker.py        # KOL whale tracking
├── risk.py               # Risk engine (hard limits + margin check)
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
5. When a trigger fires: analyze → risk check → execute → manage positions → save snapshots

---

## Key Configuration (config.py)

| Parameter | Value | Purpose |
|-----------|-------|---------|
| PAPER_WALLET_STARTING_BALANCE | $100 | Virtual capital |
| MAX_PORTFOLIO_EXPOSURE_USD | $1000 | Max total position size |
| MAX_SINGLE_POSITION_USD | $200 | Max per trade |
| MAX_LEVERAGE | 3x | Conservative leverage cap |
| MAX_CONCURRENT_POSITIONS | 3 | Position count limit |
| DEFAULT_STOP_LOSS_PCT | 5% | Auto-close losing trades |
| DEFAULT_TAKE_PROFIT_PCT | 15% | Auto-close winning trades |
| CONVICTION_THRESHOLD | 0.7 | Min confidence to trade |
| KOL_SIGNAL_BOOST | 0.15 | +15% conviction when KOL aligns |

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

---

## Known Issues / Future Work

### Issues
1. **Trade execution unverified**: hl_place_order calls may fail silently. No order ID confirmation from Hyperliquid.
2. **Boba proxy requires terminal**: Can't run headless — needs TTY for the TUI. Deployment requires workaround.
3. **Per-asset chart data**: position_snapshots table starts empty on fresh DB. Needs a few cycles to populate.

### Planned Improvements
1. **DCA/TWAP execution**: Use create_dca_order for larger positions (code scaffolded in triggers.py)
2. **Copy trading**: Use add_wallet_to_tracker to follow top KOL wallets
3. **Real wallet integration**: get_portfolio + hl_get_account for live data
4. **Deployment**: Containerize with Docker, deploy to Railway
5. **Token launch detection**: Use get_brewing_tokens for early-stage token plays
6. **Funding rate arbitrage**: Currently detects spikes but doesn't trade them
7. **Cross-chain arbitrage**: Detects price differences but doesn't execute

### API Keys & Credentials
- **Gemini**: Via Google Vertex AI (project: graphical-interface, region: us-central1)
- **Boba**: Agent ID + Secret in .env (rotate after sharing)
- **GCP Billing**: $25 trial credits on account 017671-9D851E-699CB8

---

## For the Next Agent/Developer

To continue this project:
1. Read this document first
2. Read README.md for the public-facing overview
3. Start with `config.py` to understand all parameters
4. Read `agent.py` to understand the trading pipeline
5. Read `triggers.py` to understand what drives the agent
6. The dashboard pages are self-contained — each imports from db.py and renders independently
7. The `styles/theme.py` controls all visual styling
8. Database is SQLite — `signalflow.db` in the project root
