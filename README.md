<p align="center">
  <h1 align="center">SignalFlow</h1>
  <p align="center">
    <strong>AI crypto trading agent with institutional-grade risk management</strong>
    <br />
    Prediction markets + whale tracking + funding arbitrage + on-chain discovery
    <br />
    All through one connection: <a href="https://agent.boba.xyz">Boba Agents MCP</a>
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Next.js-16-000000?style=for-the-badge&logo=next.js&logoColor=white" />
  <img src="https://img.shields.io/badge/Boba_MCP-85+_tools-6C3AED?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Gemini-2.5_Flash_Lite-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/Hyperliquid-Perps-00D4AA?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

---

Give the agent **$100**. It scans Polymarket prediction markets, tracks KOL whale wallets, monitors funding rate anomalies, discovers trending tokens, and uses **Gemini AI** to decide when to open leveraged perpetual futures trades on **Hyperliquid** &mdash; all through **Boba's unified MCP interface** (85+ tools, 9 blockchains, one connection).

Every trade passes through a **5-layer risk engine**: portfolio drawdown circuit breaker, margin enforcement, orderbook liquidity gating, ATR-based dynamic stop-loss/take-profit, and post-execution fill confirmation with slippage tracking. Positions are managed with trailing stops, AI-driven exit decisions, and hard safety limits.

---

## Table of Contents

- [System Overview](#-system-overview)
- [Data Flow](#-data-flow)
- [Signal Sources & Triggers](#-signal-sources--triggers)
- [AI Analysis Pipeline](#-ai-analysis-pipeline)
- [Risk Engine (5 Layers)](#%EF%B8%8F-risk-engine-5-layers)
- [AI-Managed Leverage](#-ai-managed-leverage)
- [Trade Execution](#-trade-execution)
- [Position Management](#-position-management)
- [Signal Interpretation](#-signal-interpretation)
- [Boba MCP Tool Catalog](#-boba-mcp-tool-catalog)
- [Dashboard (6 Pages)](#-dashboard-6-pages)
- [Tech Stack](#%EF%B8%8F-tech-stack)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [License](#-license)

---

## Overview

SignalFlow is a systematic AI crypto trading agent managing a **$100 paper portfolio** on Hyperliquid perpetual futures. It combines four distinct intelligence sources into a unified trading system:

| Intelligence Source | What It Provides |
|---|---|
| **Polymarket** | Prediction market probability shifts as leading indicators |
| **KOL Whale Tracking** | Smart-money wallet activity and directional conviction |
| **Funding Rate Arbitrage** | Cross-exchange rate divergence signals |
| **On-Chain Token Discovery** | Trending tokens and launchpad graduation events |

All data flows through **Boba Agents MCP** &mdash; a single connection that provides access to 85+ tools across 9 blockchains. No separate API keys for each data source. No custom integrations. One SDK, everything connected.

---

## Data Flow

```
+------------------------------------------------------------------+
|                    6 AUTONOMOUS TRIGGERS                          |
|                                                                   |
|  Polymarket    KOL Whales    Funding Rates                       |
|  (every 40s)   (every 50s)   (every 75s)                        |
|                                                                   |
|  Token Discovery   Cross-Chain    Portfolio Sync                 |
|  (every 100s)      (every 150s)   (every 240s)                  |
+------------------------------------------------------------------+
                            |
                            v
                  +--------------------+
                  |     EVENT BUS      |
                  |  (asyncio.Queue)   |
                  +--------------------+
                            |
                            v
                  +--------------------+
                  |    AGENT LOOP      |
                  |  (handle_event)    |
                  +--------------------+
                            |
                            v
                  +--------------------+
                  |  GEMINI ANALYSIS   |
                  | Structured prompt  |
                  | + Boba tool calls  |
                  +--------------------+
                            |
                            v
                  +--------------------+
                  | 5-LAYER RISK ENGINE|
                  |  (Pure Python)     |
                  +--------------------+
                            |
                            v
                  +--------------------+
                  | HYPERLIQUID EXEC   |
                  |  (via Boba MCP)    |
                  +--------------------+
                            |
                            v
                  +--------------------+
                  | POSITION MGMT     |
                  | SL/TP/Trailing/AI  |
                  +--------------------+
                            |
                            v
                  +--------------------+
                  |  SQLite + Next.js  |
                  |    Dashboard       |
                  +--------------------+
```

---

## Signal Sources & Triggers

The agent runs **6 autonomous triggers** on staggered intervals, each producing events that flow into the central event bus.

### 1. Polymarket Trigger (every 40s)

Scans prediction markets for significant probability movements that signal shifting market sentiment.

- **Tools**: `pm_search_markets` + `pm_get_price_history`
- **Categories scanned**: crypto, bitcoin, ethereum, defi, regulation, SEC, ETF, solana (8 total)
- **Threshold**: 4%+ probability move
- **Filters**: 8-92% probability band (ignores settled or near-certain markets)
- **Deduplication**: Same market suppressed for 8 minutes

### 2. KOL Whale Trigger (every 50s)

Monitors smart-money wallets for directional conviction signals.

- **Tool**: `get_kol_swaps`
- **Minimum trade size**: $300+
- **Extraction**: Asset, direction, size
- **Deduplication**: Same wallet + asset suppressed for 20 minutes
- **Conviction boost**: When a whale trade aligns with the agent's signal (same asset, same direction, within 60 minutes), conviction receives a **+15% boost**

### 3. Funding Rate Trigger (every 75s)

Detects funding rate divergence between Hyperliquid and Binance.

- **Tool**: `hl_get_predicted_funding`
- **Threshold**: >0.01% difference between HL and Binance predicted rates
- **Logic**:
  - HL funding very positive (longs paying shorts) &rarr; **SHORT** (fade crowded longs)
  - HL funding very negative (shorts paying longs) &rarr; **LONG** (fade crowded shorts)

### 4. Token Discovery Trigger (every 100s)

Surfaces trending and emerging tokens for awareness.

- **Tools**: `search_tokens` + `get_brewing_tokens`
- **Criteria**: >50% gain in 24h with >$100k volume, OR launchpad tokens at >80% graduation progress
- **Status**: Currently informational (logged, not auto-traded)

### 5. Cross-Chain Trigger (every 150s)

Compares ETH prices across Ethereum, Base, and Arbitrum to detect cross-chain arbitrage opportunities.

- **Tool**: `get_token_price`
- **Threshold**: >0.3% price difference across chains
- **Status**: Currently informational

### 6. Portfolio Trigger (every 240s)

Synchronizes the agent's internal state with the actual wallet.

- **Tool**: `get_portfolio`

---

## AI Analysis Pipeline

When a signal arrives, the agent runs a structured analysis inspired by institutional quant desk workflows. The AI engine is **Gemini 2.5 Flash Lite** (4K RPM, unlimited requests/day).

### Step 1 &mdash; Context Snapshot

Market regime assessment: risk-on vs risk-off, trending vs ranging. Sets the frame for all subsequent analysis.

### Step 2 &mdash; Signal Quality (Dog vs Tail)

A three-part signal decomposition:

| Component | What It Examines |
|---|---|
| **DOG (Spot/Structure)** | 4H chart structure, support/resistance levels, EMA alignment |
| **TAIL (Derivatives)** | Hyperliquid funding rate, order book depth, open interest |
| **SENTIMENT** | Polymarket probability shift + holder concentration changes |

### Step 3 &mdash; Hypothesis Generation

| Field | Description |
|---|---|
| **THESIS** | Clear directional view with a specific catalyst |
| **EDGE TYPE** | Flow (smart money), Mean Reversion (fading extremes), Narrative (catalyst), or Sentiment (contrarian) |
| **EDGE DEPTH** | Deep (structural, multi-factor) or Shallow (tactical, single signal) |
| **INVALIDATION** | Specific price level that kills the thesis |

### Step 4 &mdash; Decision Output

The AI returns structured JSON:

```json
{
  "conviction": 0.72,
  "direction": "LONG",
  "asset": "BTC",
  "size": 25.0,
  "leverage": 4,
  "hold_hours": 3,
  "reasoning": "...",
  "risk_notes": "..."
}
```

### Conviction Calibration

| Range | Meaning | Action |
|---|---|---|
| **0.0 - 0.3** | No edge | Skip |
| **0.3 - 0.5** | Weak, single factor | Trade only if R:R > 2:1 |
| **0.5 - 0.7** | Moderate, 2+ factors align | Standard trade |
| **0.7 - 0.9** | Strong, multiple factors converge | Full size |
| **0.9 - 1.0** | Exceptional, rare | Maximum conviction |

### Boba Tools Available During Analysis

Gemini can call **any** of the 85+ Boba tools as function calls during analysis. Commonly used:

`pm_get_top_holders` | `pm_get_comments` | `hl_get_asset` | `hl_get_markets` | `hl_get_history` | `hl_get_orderbook` | `hl_get_predicted_funding`

---

## Risk Engine (5 Layers)

The risk engine is **pure Python** &mdash; no LLM can override it. Every trade must pass all 5 layers sequentially.

### Layer 1 &mdash; Portfolio Drawdown Circuit Breaker

Tracks peak balance in real-time and enforces portfolio-level protection.

| Drawdown | Action |
|---|---|
| < 15% | Normal trading |
| 15% - 30% | **Halve** all new position sizes |
| > 30% | **HALT** all trading for 4 hours |

### Layer 2 &mdash; Position Limits & Margin Enforcement

| Rule | Value |
|---|---|
| Max concurrent positions | 8 |
| Cash reserve | 10% (always kept free) |
| Max margin per trade | 30% of balance |
| Anti-churn cooldown | 3 minutes between same-asset trades |
| Direction flip cooldown | 10 minutes before reversing on same asset |

### Layer 3 &mdash; Orderbook Liquidity Gate

Before every trade, fetches live orderbook data via `hl_get_orderbook`:

- Requires **$500+ depth** at top 5 levels
- Estimates slippage via volume-weighted average price
- **Rejects** trade if estimated slippage > 5%

### Layer 4 &mdash; ATR Dynamic Stops

Computes **14-period ATR** from 1H candles via `hl_get_history`, then sets adaptive stops:

| Parameter | Formula | Cap |
|---|---|---|
| **Stop-Loss** | ATR x 1.5 | 5% of entry |
| **Take-Profit** | ATR x 3.0 | 12% of entry |
| **Risk:Reward** | Always 2:1 minimum | &mdash; |
| **Fallback** | Fixed 5% SL / 10% TP | If ATR unavailable |
| **Trailing Stop** | When PnL > 5%, SL moves to break-even | &mdash; |

### Layer 5 &mdash; Fill Confirmation & Slippage Tracking

After every market order executes:

1. Calls `hl_get_fills` to confirm actual fill price
2. Calculates realized slippage vs expected
3. Adjusts SL/TP based on **actual entry**, not expected price

### Risk Layers Summary

| Layer | Purpose | Boba Tool |
|---|---|---|
| 1. Drawdown Breaker | Portfolio-level circuit breaker | &mdash; (custom) |
| 2. Margin & Limits | Position-level caps & cooldowns | &mdash; (custom) |
| 3. Orderbook Gate | Pre-trade liquidity verification | `hl_get_orderbook` |
| 4. ATR Dynamic Stops | Volatility-aware SL/TP | `hl_get_history` |
| 5. Fill Confirmation | Post-trade slippage tracking | `hl_get_fills` |

---

## AI-Managed Leverage

Leverage is **not static**. The AI suggests leverage per trade, and the risk engine enforces conviction-based caps:

| Conviction | Max Leverage | Rationale |
|---|---|---|
| < 0.4 | **2x** | Low confidence &mdash; stay safe |
| 0.4 - 0.6 | **3x** | Moderate edge |
| 0.6 - 0.8 | **5x** | Strong edge, multiple factors |
| > 0.8 | **7x** | Exceptional edge, full conviction |

---

## Trade Execution

Every trade follows a 5-step execution sequence through Boba MCP:

```
1. hl_update_leverage(coin, leverage, isCross=true)   -- Set leverage
2. hl_place_order(coin, side, size, type="market")     -- Market entry
3. hl_get_fills(limit=5)                               -- Confirm fill & slippage
4. hl_place_order(type="stop", triggerPrice=SL)        -- Stop-loss order
5. hl_place_order(type="take_profit", triggerPrice=TP) -- Take-profit order
```

### Position Sizing Formula

```
sized  = suggested_size * conviction
capped = min(sized, balance * 0.30 * 3)       # 30% margin * 3x leverage
if drawdown >= 15%: capped *= 0.5              # halve during warning zone
if capped < $8: reject                         # dust filter
```

---

## Position Management

For each open position, every cycle the agent:

| Check | Condition | Action |
|---|---|---|
| **Price update** | Every cycle | Fetch via `hl_get_asset`, calculate unrealized PnL, save snapshot |
| **Hard stop-loss** | Price hits SL | `hl_close_position` immediately, status = STOPPED |
| **Hard take-profit** | Price hits TP | Close immediately, status = CLOSED |
| **Trailing stop** | PnL > 5% | Move SL to break-even (entry x 1.005) |
| **Planned hold check** | Age >= planned hold_hours | Ask Gemini: "Should I close?" &mdash; AI checks trend, funding, whale flows, sentiment |
| **Smart early exit** | Age >= 50% of hold AND losing > 2% | AI evaluates early close |
| **Hard age limit** | Position older than 8 hours | Force-close (safety net) |

---

## Signal Interpretation

The agent understands prediction market semantics &mdash; probability direction alone is not enough:

| Market Question | Probability Change | Interpretation |
|---|---|---|
| "Will BTC dip below $60k?" | **Falls** | Market thinks dip less likely &rarr; **BULLISH** |
| "Will BTC dip below $60k?" | **Rises** | Market thinks dip more likely &rarr; **BEARISH** |
| "Will SOL reach $110?" | **Rises** | Market more bullish on target &rarr; **BULLISH** |
| "Will SOL reach $110?" | **Falls** | Target less likely, but NOT necessarily bearish. Cross-reference with spot price and funding rates. |

---

## Boba MCP Tool Catalog

### Signal Detection & Market Intelligence

| Tool | Purpose |
|---|---|
| `pm_search_markets` | Find prediction markets by category (crypto, bitcoin, ETF, etc.) |
| `pm_get_price_history` | Detect probability movements over time |
| `pm_get_top_holders` | Whale positioning in prediction markets |
| `pm_get_comments` | Community sentiment and narrative signals |
| `get_kol_swaps` | KOL wallet trades (direction, size, asset) |
| `search_tokens` | Trending token discovery (gain + volume filters) |
| `get_brewing_tokens` | Launchpad tokens nearing graduation |
| `get_token_price` | Cross-chain price comparison (ETH/Base/Arbitrum) |
| `audit_token` | Security audit for token safety |

### Execution & Risk Management

| Tool | Purpose |
|---|---|
| `hl_get_asset` | Current Hyperliquid prices for PnL calculation |
| `hl_get_markets` | Market search and asset discovery |
| `hl_get_history` | OHLCV candles for **ATR-based dynamic SL/TP** calculation |
| `hl_get_orderbook` | L2 depth for **pre-trade liquidity gating** |
| `hl_get_predicted_funding` | Funding rates for signal generation + analysis |
| `hl_place_order` | Execute trades (market, stop, take_profit) |
| `hl_update_leverage` | Set per-trade leverage |
| `hl_close_position` | Atomic position closing (no dust) |
| `hl_get_fills` | **Fill confirmation & realized slippage tracking** |

### Portfolio & Wallet

| Tool | Purpose |
|---|---|
| `get_portfolio` | Real wallet state synchronization |

> All 85+ Boba tools are also exposed to Gemini during analysis, enabling the AI to autonomously call any tool it needs for deeper research.

---

## Dashboard (6 Pages)

### 1. Landing Page
Architecture overview, signal pipeline visualization, strategy explanations, and tech stack showcase.

### 2. Command Center
Live pipeline status, key performance metrics, Boba API connection health, real-time signal feed, and AI reasoning display.

### 3. Portfolio
Wallet value chart with per-position lines, buy/sell markers on the timeline, risk metrics (Profit Factor, Max Drawdown, Sharpe Ratio), open positions table, and full trade history with AI reasoning for each decision.

### 4. Market Scanner
Signal type breakdown, price change distribution histogram, filterable signal feed with inline AI analysis for each signal.

### 5. Agent Performance
Conviction vs PnL scatter plot, asset allocation donut chart, agent activity bar charts, win rate by asset, and full decision log.

### 6. Whale Intelligence
KOL volume by asset, activity timeline, signal correlation table (Polymarket match + directional alignment), and real-time whale feed.

---

## Tech Stack

| Component | Technology | Role |
|---|---|---|
| **Trading Infrastructure** | [Boba Agents MCP](https://agent.boba.xyz) | 85+ tools, 9 blockchains, single connection |
| **AI Engine** | Gemini 2.5 Flash Lite | Decision engine (4K RPM, unlimited/day) |
| **Perps Exchange** | Hyperliquid | Perpetual futures execution |
| **Prediction Markets** | Polymarket | Probability-based signal source |
| **Agent Core** | Python 3.11+ | asyncio event loop, Pydantic v2 models |
| **Web Dashboard** | Next.js 16 | Recharts, Tailwind CSS, boba.xyz theme |
| **Streamlit Dashboard** | Streamlit + Plotly | Alternative visual interface |
| **Database** | SQLite (WAL mode) | Concurrent read/write persistence |
| **Deployment** | Docker + docker-compose | Production-ready containerization |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for Next.js dashboard)
- A [Boba](https://agent.boba.xyz) account with API credentials
- A Google AI API key (for Gemini)

### 1. Clone & Install

```bash
git clone https://github.com/your-org/signalflow.git
cd signalflow
pip install google-genai mcp pydantic python-dotenv streamlit pandas plotly
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_key
BOBA_API_KEY=your_boba_key
BOBA_AGENT_ID=your_agent_id
BOBA_AGENT_SECRET=your_agent_secret
```

### 3. Start the Agent

```bash
python runner.py
```

### 4. Start the Dashboard

**Next.js dashboard** (recommended):

```bash
cd web && npm install && npm run dev
```

**Streamlit dashboard** (alternative):

```bash
streamlit run dashboard.py
```

### Docker Deployment

```bash
docker-compose up --build -d
# Dashboard at http://localhost:3000 (Next.js) or http://localhost:8501 (Streamlit)
# Logs: docker-compose logs -f agent
```

---

## Project Structure

```
signalflow/
  runner.py             Entry point -- event loop with Boba retry/reconnect
  agent.py              Core brain -- analyze, execute, manage positions
  risk.py               5-layer risk engine (ATR, drawdown, orderbook, margin, fills)
  signals.py            Polymarket signal detection + dead market filter
  kol_tracker.py        KOL whale tracking via Boba
  triggers.py           6 async triggers with exponential backoff
  event_bus.py          asyncio.Queue connecting triggers to agent
  mcp_client.py         Boba MCP connection wrapper
  config.py             All parameters in one place
  models.py             Pydantic v2 data models
  db.py                 SQLite persistence (WAL mode, indexed)
  seed_data.py          Demo data generator
  dashboard.py          Streamlit multi-page app entry point
  pages/
    00_landing.py       Landing page -- architecture & Boba showcase
    01_overview.py      Command center -- pipeline & metrics
    02_portfolio.py     Portfolio -- wallet growth + per-position charts
    03_signals.py       Market scanner with filtering
    04_analytics.py     Agent performance -- conviction vs PnL
    05_kol_tracker.py   Whale intelligence
  styles/
    theme.py            Dark theme + Plotly defaults
  web/                  Next.js 16 dashboard (Recharts, Tailwind)
  Dockerfile            Multi-stage build (Node.js + Python)
  docker-compose.yml    Agent + dashboard services
  run.sh                One-command launcher
```

---

## License

MIT
