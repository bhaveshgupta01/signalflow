# SignalFlow — Technical Product Requirements Document

**Version**: 6.0
**Last Updated**: 2026-04-07
**Status**: Production (Paper Trading)
**Classification**: Internal Technical Document

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Tech Stack](#3-tech-stack)
4. [Data Flow & Decision Pipeline](#4-data-flow--decision-pipeline)
5. [Signal Detection Layer](#5-signal-detection-layer)
6. [AI Analysis Engine](#6-ai-analysis-engine)
7. [Risk Management Engine](#7-risk-management-engine)
8. [Execution Engine](#8-execution-engine)
9. [Position Management](#9-position-management)
10. [Event System](#10-event-system)
11. [MCP Integration Layer](#11-mcp-integration-layer)
12. [Data Persistence](#12-data-persistence)
13. [Dashboard & Observability](#13-dashboard--observability)
14. [Deployment Architecture](#14-deployment-architecture)
15. [Configuration Reference](#15-configuration-reference)
16. [API & Tool Inventory](#16-api--tool-inventory)
17. [Error Handling & Resilience](#17-error-handling--resilience)
18. [Performance Characteristics](#18-performance-characteristics)
19. [Security Considerations](#19-security-considerations)
20. [Known Limitations & Roadmap](#20-known-limitations--roadmap)

---

## 1. Executive Summary

### 1.1 Product Definition

SignalFlow is an **autonomous, event-driven AI trading agent** that manages a $100 virtual portfolio by trading perpetual futures on Hyperliquid. It ingests signals from 6 independent data sources (prediction markets, whale wallets, funding rates, token trends, cross-chain pricing, portfolio state), evaluates them using a Gemini 2.5 Flash LLM with access to 85+ on-chain tools, and executes trades through a 5-layer institutional-grade risk pipeline.

### 1.2 Core Thesis

Polymarket prediction markets reflect crowd-sourced probabilistic assessments of future events. When a crypto-related prediction market moves sharply (e.g., "Will BTC dip to $50K?" probability drops 30% in 15 minutes), it signals a real-time shift in collective market intelligence. SignalFlow captures this edge by translating prediction market sentiment into directional perpetual futures trades, validated by whale wallet activity and funding rate data.

### 1.3 Key Metrics

| Metric | Value |
|--------|-------|
| Initial Capital | $100 (paper) |
| Boba Tools Available | 85+ |
| Boba Tools Directly Integrated | 22 |
| Signal Sources | 6 independent async triggers |
| Risk Layers | 5 (drawdown, margin, orderbook, ATR stops, fill confirmation) |
| Max Concurrent Positions | 5 |
| Max Leverage | 3x |
| Trade Assets | BTC, ETH, SOL (+ any Hyperliquid perp) |
| Dashboard Pages | 6 |

### 1.4 Design Principles

1. **Hard risk gates over AI judgment** — The LLM can suggest trades but cannot override position limits, margin rules, or stop-losses. Risk enforcement is deterministic Python code.
2. **Event-driven over polling** — Triggers emit events asynchronously. The agent processes them in FIFO order. No wasted cycles.
3. **Fail safe over fail open** — If any risk check fails or data is unavailable, the trade is rejected. If Gemini times out, partial results are returned. If Boba disconnects, exponential backoff + reconnect.
4. **Transparency over black-box** — Every signal, analysis, trade, and position snapshot is persisted. The dashboard renders the full decision chain.

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL DATA SOURCES                        │
│                                                                     │
│   Polymarket        KOL Wallets (429)     Hyperliquid Exchange      │
│   Prediction        Whale Trade           Perps, Funding Rates,     │
│   Markets           Monitoring            Orderbook, Candles        │
│                                                                     │
│   Token Discovery   Cross-Chain           Portfolio State            │
│   Trending Tokens   ETH Price Diffs       Wallet Balances            │
└─────────────┬──────────────┬──────────────┬─────────────────────────┘
              │              │              │
              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     BOBA AGENTS MCP SERVER                          │
│                                                                     │
│   Single MCP endpoint exposing 85+ tools across 9 blockchains       │
│   Handles: auth, rate limiting, chain routing, data normalization    │
│   Protocol: Model Context Protocol (stdio or SSE transport)         │
│   Tools: pm_*, hl_*, get_kol_*, search_tokens, audit_token, etc.    │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SIGNALFLOW AGENT RUNTIME                        │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │              6 ASYNC TRIGGER TASKS                       │        │
│  │                                                         │        │
│  │  polymarket_trigger   (45s)  ──┐                        │        │
│  │  kol_trigger          (60s)  ──┤                        │        │
│  │  funding_trigger      (90s)  ──┤  Events                │        │
│  │  token_discovery     (120s)  ──┼──────────┐             │        │
│  │  cross_chain_trigger (180s)  ──┤          │             │        │
│  │  portfolio_trigger   (300s)  ──┘          │             │        │
│  └───────────────────────────────────────────┼─────────────┘        │
│                                              ▼                      │
│  ┌───────────────────────────────────────────────────────┐          │
│  │                 EVENT BUS (asyncio.Queue)              │          │
│  │          FIFO ordering  |  Backpressure handling       │          │
│  └───────────────────────────┬───────────────────────────┘          │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────┐          │
│  │               AGENT BRAIN (agent.py)                  │          │
│  │                                                       │          │
│  │  ┌─── Phase 1: SIGNAL ENRICHMENT ──────────────────┐  │          │
│  │  │  pm_get_top_holders → whale positioning          │  │          │
│  │  │  pm_get_comments → community sentiment           │  │          │
│  │  │  Semantic interpretation of market question       │  │          │
│  │  └────────────────────────┬────────────────────────┘  │          │
│  │                           ▼                           │          │
│  │  ┌─── Phase 2: AI ANALYSIS ────────────────────────┐  │          │
│  │  │  Gemini 2.5 Flash + 85 Boba tools               │  │          │
│  │  │  → conviction (0.0-1.0), direction, asset        │  │          │
│  │  │  → sizing, leverage, hold time, reasoning        │  │          │
│  │  │  KOL conviction boost (+10% if whale aligned)    │  │          │
│  │  └────────────────────────┬────────────────────────┘  │          │
│  │                           ▼                           │          │
│  │  ┌─── Phase 3: 5-LAYER RISK GATE ─────────────────┐  │          │
│  │  │  L1: Drawdown breaker (halt at -20%)            │  │          │
│  │  │  L2: Margin + position limits (5 max, 25% cap)  │  │          │
│  │  │  L3: Orderbook depth (hl_get_orderbook)         │  │          │
│  │  │  L4: ATR dynamic stops (hl_get_history)         │  │          │
│  │  │  L5: Conviction threshold (≥ 0.75)              │  │          │
│  │  └────────────────────────┬────────────────────────┘  │          │
│  │                           ▼                           │          │
│  │  ┌─── Phase 4: EXECUTION ─────────────────────────┐  │          │
│  │  │  hl_update_leverage → hl_place_order (market)   │  │          │
│  │  │  hl_get_fills → fill confirmation + slippage    │  │          │
│  │  │  hl_place_order (stop) + hl_place_order (TP)    │  │          │
│  │  └────────────────────────┬────────────────────────┘  │          │
│  │                           ▼                           │          │
│  │  ┌─── Phase 5: POSITION MANAGEMENT ───────────────┐  │          │
│  │  │  Every cycle: check SL/TP/trailing/age          │  │          │
│  │  │  hl_close_position for all exits (atomic)       │  │          │
│  │  │  AI exit decisions at planned hold time          │  │          │
│  │  │  Snapshot PnL for dashboard charts               │  │          │
│  │  └────────────────────────────────────────────────┘  │          │
│  └───────────────────────────────────────────────────────┘          │
│                              │                                      │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────┐          │
│  │           SQLite Database (WAL mode)                   │          │
│  │  7 tables: signals, analyses, positions,               │          │
│  │  position_snapshots, wallet_snapshots,                 │          │
│  │  kol_signals, agent_decisions                          │          │
│  └───────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   STREAMLIT DASHBOARD (6 pages)                     │
│                                                                     │
│   00_landing     01_overview    02_portfolio                        │
│   Project info   Pipeline       Wallet growth                       │
│   Risk layers    status +       + per-trade                         │
│   Boba showcase  metrics        line charts                         │
│                                                                     │
│   03_signals     04_analytics   05_kol_tracker                     │
│   Market         Conviction     Whale wallet                        │
│   scanner +      vs PnL         timeline +                          │
│   AI reasoning   analysis       alignment                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Dependency Graph

```
runner.py (entrypoint)
  ├── mcp_client.py  → Boba MCP (stdio/SSE)
  ├── google.genai   → Gemini 2.5 Flash (Vertex AI / API key)
  ├── event_bus.py   → asyncio.Queue
  ├── triggers.py    → 6 async tasks
  │     ├── signals.py      → pm_search_markets, pm_get_price_history
  │     └── kol_tracker.py  → get_kol_swaps
  ├── agent.py       → Core decision engine
  │     ├── risk.py         → 5-layer risk pipeline
  │     │     └── hl_get_history, hl_get_orderbook, hl_get_fills
  │     ├── db.py           → SQLite persistence
  │     └── models.py       → Pydantic v2 schemas
  └── db.py          → init_db()
```

### 2.3 Process Architecture

```
┌──────────────────────┐     ┌──────────────────────┐
│   Agent Process       │     │   Dashboard Process   │
│   (runner.py)         │     │   (streamlit)         │
│                       │     │                       │
│   1 main loop         │     │   6 page modules      │
│   6 trigger tasks     │     │   10s auto-refresh    │
│   ~1 Gemini call/min  │     │   Read-only DB access │
│                       │     │                       │
│   Writes: signals,    │     │   Reads: all tables   │
│   analyses, positions,│◄────┤   via db.py           │
│   snapshots           │ DB  │                       │
└──────────────────────┘     └──────────────────────┘
```

Both processes access the same SQLite database. WAL (Write-Ahead Logging) mode allows concurrent reads from the dashboard while the agent writes.

---

## 3. Tech Stack

### 3.1 Core Runtime

| Component | Technology | Version | Role |
|-----------|-----------|---------|------|
| Language | Python | 3.11+ | Agent logic, risk engine, dashboard |
| AI Model | Gemini 2.5 Flash | Latest | Signal analysis, tool calling, exit decisions |
| AI Platform | Google Vertex AI | v1 | Model hosting, billing, rate limits |
| AI SDK | google-genai | Latest | Python client for Gemini |
| MCP Server | Boba Agents | @tradeboba/cli@latest | 85+ trading tools, 9 blockchains |
| MCP Protocol | Model Context Protocol | 1.0 | Tool discovery, invocation, transport |
| Database | SQLite | 3.x (WAL mode) | 7 tables, 7 indexes, single-file persistence |
| Dashboard | Streamlit | Latest | 6-page interactive UI |
| Charts | Plotly | Latest | Interactive line/scatter/bar charts |
| Validation | Pydantic | v2 | 8 data models with type enforcement |
| Async | asyncio | stdlib | Event bus, concurrent triggers |

### 3.2 External Services

| Service | Purpose | Connection |
|---------|---------|------------|
| Boba MCP | 85+ trading tools (Polymarket, Hyperliquid, wallet tracking, etc.) | stdio (local) or SSE (remote) |
| Google Vertex AI | Gemini 2.5 Flash model hosting | gRPC via google-genai SDK |
| Hyperliquid | Perpetual futures exchange (execution) | via Boba `hl_*` tools |
| Polymarket | Prediction markets (signal source) | via Boba `pm_*` tools |

### 3.3 Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Container | Docker (multi-stage) | Node.js + Python in single image |
| Orchestration | docker-compose | Agent + dashboard as services |
| Deployment | Railway / any Docker host | One-command deploy |
| Config | python-dotenv | .env-based secret management |

---

## 4. Data Flow & Decision Pipeline

### 4.1 Complete Trade Lifecycle

```
                    ┌─────────────────────────┐
                    │   EXTERNAL DATA SOURCE   │
                    │   (Polymarket/KOL/etc.)  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      TRIGGER TASK        │
                    │   Polls at fixed interval │
                    │   Applies basic filters   │
                    │   Emits Event to bus      │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │       EVENT BUS          │
                    │   asyncio.Queue (FIFO)   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   SIGNAL ENRICHMENT      │
                    │   pm_get_top_holders     │
                    │   pm_get_comments        │
                    │   Semantic interpretation │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   GEMINI ANALYSIS        │
                    │   System prompt + signal  │
                    │   + 85 Boba tools         │
                    │   Max 10 tool rounds      │
                    │   45s timeout             │
                    │                          │
                    │   Output:                │
                    │   conviction, direction,  │
                    │   asset, size, leverage,  │
                    │   hold_hours, reasoning   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   KOL ALIGNMENT CHECK    │
                    │   +10% boost if whale    │
                    │   traded same direction   │
                    │   within 60 minutes       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
              NO    │   CONVICTION ≥ 0.75?     │
           ┌────────┤                          │
           │        └────────────┬────────────┘
           │                     │ YES
           ▼                     ▼
       [SKIP]       ┌────────────────────────┐
                    │   RISK LAYER 1          │
                    │   Drawdown Breaker      │
                    │   < 10%? → proceed      │
                    │   10-20%? → halve size  │
                    │   > 20%? → HALT         │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   RISK LAYER 2          │
                    │   Margin & Limits       │
                    │   Cash reserve 20%      │
                    │   Per-trade cap 25%     │
                    │   Max 5 positions       │
                    │   No contradictions     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   TOKEN AUDIT           │
                    │   audit_token → reject  │
                    │   if high risk / scam   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   POSITION SIZING       │
                    │   size = conviction ×    │
                    │         suggested_size   │
                    │   Cap to available margin│
                    │   Halve if DD warning    │
                    │   Reject if < $20       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   RISK LAYER 3          │
                    │   Orderbook Gate        │
                    │   hl_get_orderbook      │
                    │   Depth ≥ $500?         │
                    │   Slippage ≤ 0.3%?      │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   RISK LAYER 4          │
                    │   ATR Dynamic Stops     │
                    │   hl_get_history (1H)   │
                    │   ATR(14) computation   │
                    │   SL = 1.5 × ATR        │
                    │   TP = 3.0 × ATR        │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   EXECUTION             │
                    │   hl_update_leverage    │
                    │   hl_place_order (mkt)  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   RISK LAYER 5          │
                    │   Fill Confirmation     │
                    │   hl_get_fills          │
                    │   Actual fill price     │
                    │   Slippage calculation  │
                    │   Recalculate SL/TP     │
                    │   on actual entry       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   SL/TP ORDER PLACEMENT │
                    │   hl_place_order (stop) │
                    │   hl_place_order (TP)   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   PERSIST TO DB         │
                    │   Save position         │
                    │   Save wallet snapshot  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   POSITION MANAGEMENT  │
                    │   (every subsequent     │
                    │    event cycle)         │
                    │                        │
                    │   Check SL/TP hit      │
                    │   Trailing stop (>5%)  │
                    │   AI exit at hold time │
                    │   Early exit if losing │
                    │   Hard close at 8h     │
                    │                        │
                    │   All exits via        │
                    │   hl_close_position    │
                    └────────────────────────┘
```

### 4.2 Decision Matrix

| Signal Type | Conviction Formula | Trade Action |
|-------------|-------------------|--------------|
| Polymarket 8%+ move | Gemini analysis (0.0-1.0) | Trade if ≥ 0.75 |
| Polymarket + KOL aligned | Base conviction + 0.10 | Boosted trade |
| Funding rate spike (>0.05%) | `min(0.85, 0.6 + |diff| × 100)` | Synthetic signal, trade if ≥ 0.75 |
| Token discovery | Logged only (v6) | No auto-trade |
| Cross-chain opportunity | Logged only (v6) | No auto-trade |
| Portfolio update | Wallet sync only | No trade |

---

## 5. Signal Detection Layer

### 5.1 Polymarket Signal Detection (`signals.py`)

**Input**: 8 category keywords scanned across Polymarket
**Output**: `Signal` objects persisted to DB

```
Categories: crypto, bitcoin, ethereum, defi, regulation, SEC, ETF, solana
```

**Pipeline**:
1. For each category → `pm_search_markets(q=category, limit=10)`
2. For each market → extract Yes token price and token ID
3. Fetch 24H price history → `pm_get_price_history(market=tokenId, interval="1d", fidelity=24)`
4. Calculate percentage change from first to last data point
5. **Filters** (all must pass):
   - `|price_change| ≥ 8%` (MIN_SIGNAL_PRICE_CHANGE)
   - `0.02 < yes_price < 0.98` (skip resolved/dead markets)
   - No signal for this market in last 15 minutes (dedup)
6. Save to `signals` table
7. Return list for agent processing

### 5.2 Semantic Signal Interpretation

The agent applies semantic understanding to prediction market questions:

| Market Question Pattern | Price Change | Interpretation |
|------------------------|-------------|----------------|
| "Will BTC **dip** to $50K?" | Price **drops** | Dip less likely → **BULLISH** |
| "Will BTC **dip** to $50K?" | Price **rises** | Dip more likely → **BEARISH** |
| "Will BTC **reach** $80K?" | Price **rises** | Rally more likely → **BULLISH** |
| "Will BTC **reach** $80K?" | Price **drops** | Rally less likely → **BEARISH** |

This interpretation hint is injected into the Gemini prompt to prevent inverted analysis.

### 5.3 KOL Whale Tracking (`kol_tracker.py`)

**Input**: `get_kol_swaps(limit=30)` from Boba
**Output**: `KolSignal` objects persisted to DB

**Pipeline**:
1. Fetch recent KOL swap activity
2. Extract: wallet, asset, size_usd, direction
3. **Map DEX tokens to Hyperliquid-tradable assets** (26 supported: BTC, ETH, SOL, DOGE, etc.)
4. Solana memecoin trades → mapped to SOL (the chain's native asset)
5. **Filters**:
   - `size_usd ≥ $500` (KOL_MIN_TRADE_USD)
   - Not seen in last 30 minutes (dedup by wallet + asset + direction)
6. Save to `kol_signals` table

**Conviction Boost Logic**: When the agent analyzes a Polymarket signal, it checks `kol_signals` for the last 60 minutes. If any KOL traded the same asset in the same direction:
- Conviction += 0.10 (capped at 1.0)
- KOL names appended to analysis reasoning

---

## 6. AI Analysis Engine

### 6.1 Model Configuration

| Parameter | Value |
|-----------|-------|
| Model | `gemini-2.5-flash` |
| Platform | Google Vertex AI (project: graphical-interface, region: us-central1) |
| Temperature | 0.4 |
| Max output tokens | 4096 |
| Timeout | 45 seconds per round |
| Max tool rounds | 10 |
| Function calling | Enabled (all 85 Boba tools exposed) |

### 6.2 System Prompt Design

The system prompt establishes:
1. **Identity**: Disciplined AI trading agent managing $100 paper wallet
2. **Selectivity**: "Most signals are noise — reject them"
3. **Multi-data validation**: Trade only when multiple data points align
4. **Edge requirement**: "A vague 'bullish momentum' is NOT an edge. Name the specific catalyst."
5. **Sizing guidance**: Conservative scaling with conviction (0.7 → $20-35, 0.9 → $50-80)
6. **Output schema**: Strict JSON with conviction, direction, asset, size, leverage, hold_hours, reasoning, risk_notes

### 6.3 Tool Loop Architecture

```
User message (signal + context)
         │
         ▼
┌────────────────────┐
│  Gemini generates   │ ◄──── 85 Boba tools available
│  text + tool calls  │       as function declarations
└────────┬───────────┘
         │
    ┌────┴────┐
    │ Tools?  │
    └────┬────┘
     YES │        NO
         ▼         ▼
┌──────────────┐  Return
│ Execute each │  final
│ Boba tool    │  text
│ call async   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Append tool  │
│ results to   │
│ conversation │
└──────┬───────┘
       │
       ▼
  (next round, up to 10)
```

### 6.4 Analysis Output Schema

```json
{
  "conviction": 0.80,
  "direction": "long",
  "asset": "BTC",
  "suggested_size_usd": 50.0,
  "leverage": 2,
  "hold_hours": 3.0,
  "reasoning": "Polymarket 'BTC dip to $50K' probability dropped 27% in 15 min...",
  "risk_notes": "Polymarket event covers entire April. Unexpected macro news could reverse."
}
```

---

## 7. Risk Management Engine

### 7.1 5-Layer Risk Pipeline

All layers execute sequentially. Failure at any layer rejects the trade. No LLM can override.

#### Layer 1: Portfolio Drawdown Circuit Breaker

| Drawdown Level | Action | Recovery |
|---------------|--------|----------|
| < 10% | Normal trading | — |
| 10% - 20% | All new position sizes halved | Automatic when balance recovers |
| ≥ 20% | **All new trades halted** | 6-hour cooldown timer |

**Implementation**: Tracks `_peak_balance` in memory. Checked on every `can_open_position()` call.

```
drawdown = (peak_balance - current_balance) / peak_balance
```

#### Layer 2: Margin & Position Limits

| Rule | Constraint |
|------|-----------|
| Cash reserve | 20% of balance always free |
| Per-trade maximum | 25% of balance (margin) |
| Concurrent positions | Max 5 |
| Leverage cap | Max 3x (clamped in code) |
| Contradictory positions | Cannot hold long + short on same asset |
| Flip cooldown | 30 minutes between closing and reversing |
| Minimum trade | $20 (reject dust) |

**Position Size Formula**:
```
sized = suggested_size × conviction
max_margin = balance × 0.25
capped = min(sized, max_margin × 3)
if margin_for_capped > available_margin:
    capped = available_margin × 3
if drawdown ≥ 10%:
    capped = capped × 0.5
if capped < 20:
    reject
```

#### Layer 3: Orderbook Liquidity Gate

**Boba Tool**: `hl_get_orderbook(coin=ASSET)`

| Check | Threshold | Action if Failed |
|-------|-----------|------------------|
| Top-of-book depth | ≥ $500 USD | Reject trade |
| Estimated slippage | ≤ 0.3% | Reject trade |

**Slippage Estimation**: Compare volume-weighted average price (VWAP) across top 3-5 levels against mid-price:
```
mid_price = (best_bid + best_ask) / 2
vwap = sum(price × size for top levels) / sum(size for top levels)
slippage = |vwap - mid_price| / mid_price
```

#### Layer 4: ATR-Based Dynamic Stops

**Boba Tool**: `hl_get_history(coin=ASSET, type="candles", interval="1h", limit=19)`

**ATR(14) Computation**:
```
For each candle (i > 0):
    true_range = max(high - low, |high - prev_close|, |low - prev_close|)
ATR = mean(last 14 true_ranges)
```

**Stop Placement**:
```
LONG:  SL = entry - ATR × 1.5    TP = entry + ATR × 3.0
SHORT: SL = entry + ATR × 1.5    TP = entry - ATR × 3.0
```

**Fallback**: If candle data unavailable → fixed 5% SL, 10% TP.

**Why ATR**: A flat 5% stop on BTC (~2-3% daily vol) is 2 days of movement. On SOL (~5-8% daily vol) it gets hit by intraday noise. ATR scales stops to each asset's actual volatility.

#### Layer 5: Fill Confirmation & Slippage Tracking

**Boba Tool**: `hl_get_fills(coin=ASSET, limit=5)`

Post-execution:
1. Fetch most recent fill for the asset
2. Compare fill price to expected entry price
3. Calculate slippage: `(fill_price - expected) / expected`
4. If fill price differs → **recalculate SL/TP on actual entry price**
5. Log slippage; warn if > 0.3%

### 7.2 Position Closing

All exit paths use **`hl_close_position(coin=ASSET)`** — atomic close, guaranteed no dust. Applies to:
- Stop-loss hit
- Take-profit hit
- Planned exit (AI decision)
- Early exit (losing at 50% planned hold)
- Max age limit (8 hours)
- Position flip (close old, open new direction)

---

## 8. Execution Engine

### 8.1 Trade Execution Sequence

```
1. hl_update_leverage(coin, leverage, mode="cross")
2. [Layer 3] hl_get_orderbook(coin) → liquidity check
3. [Layer 4] hl_get_history(coin, candles, 1h) → ATR computation → SL/TP
4. hl_place_order(coin, side, size, type="market")
5. [Layer 5] hl_get_fills(coin) → confirm fill, track slippage
6. Recalculate SL/TP if fill price differs
7. hl_place_order(coin, sl_side, size, type="stop", triggerPrice=SL)
8. hl_place_order(coin, sl_side, size, type="take_profit", triggerPrice=TP)
9. Save Position to database
```

### 8.2 Fallback Execution

If direct execution fails (steps 1-8), the agent falls back to a **Gemini tool loop**: sends a structured TRADE_PROMPT to Gemini with the trade parameters, and lets Gemini autonomously call the Boba tools. This handles edge cases where tool parameters differ from expected format.

---

## 9. Position Management

### 9.1 Management Cycle

Runs on **every event** (not just trade events). For each open position:

```
1. Fetch current price (hl_get_asset)
2. Calculate unrealized PnL
3. Save position snapshot (for dashboard charts)
4. Check exit conditions (in priority order):

   ┌─ SL HIT? ─────────── → hl_close_position → STOPPED
   ├─ TP HIT? ─────────── → hl_close_position → CLOSED
   ├─ PnL > 5%? ────────── → Move SL to break-even (trailing)
   ├─ Age ≥ planned hold? ─ → Ask Gemini: close or extend?
   │                            └─ close → hl_close_position
   │                            └─ hold  → continue
   │                            └─ error → hl_close_position (safe)
   ├─ Age ≥ 50% planned    → If PnL < -2%, ask Gemini: cut losses?
   │  AND losing?              └─ close → hl_close_position
   └─ Age ≥ 8 hours? ────── → hl_close_position (hard safety net)
```

### 9.2 PnL Calculation

```python
if direction == LONG:
    pnl = (current_price - entry_price) / entry_price × size_usd × leverage
else:  # SHORT
    pnl = (entry_price - current_price) / entry_price × size_usd × leverage
```

### 9.3 Trailing Stop

When unrealized PnL > 5% of position size:
- LONG: move SL to `entry_price × 1.005` (lock 0.5% profit minimum)
- SHORT: move SL to `entry_price × 0.995`

Only triggers once (when SL is still below entry for longs / above entry for shorts).

---

## 10. Event System

### 10.1 Event Types

| TriggerType | Source | Interval | Handler |
|-------------|--------|----------|---------|
| `POLYMARKET_MOVE` | Polymarket prediction markets | 45s | Full pipeline: analyze → risk → execute |
| `KOL_WHALE_TRADE` | 429 tracked wallets | 60s | Log only (conviction boost on next analysis) |
| `FUNDING_RATE_SPIKE` | Hyperliquid vs Binance rates | 90s | Synthetic signal → pipeline (if diff > 0.05%) |
| `TOKEN_DISCOVERY` | Trending tokens + launchpad | 120s | Log only (v6) |
| `CROSS_CHAIN_OPPORTUNITY` | ETH cross-chain price diff | 180s | Log only (v6) |
| `PORTFOLIO_UPDATE` | Boba portfolio sync | 300s | Wallet state update |

### 10.2 Event Schema

```python
@dataclass
class Event:
    trigger: TriggerType       # Enum identifying source
    data: dict[str, Any]       # Trigger-specific payload
    timestamp: datetime        # UTC creation time
```

### 10.3 Backpressure & Error Handling

- **Queue**: Unbounded `asyncio.Queue` (FIFO)
- **Trigger errors**: Exponential backoff per trigger (`base_interval × 2^consecutive_errors`, capped at 600s)
- **Agent errors**: Counter tracks consecutive failures. At 10 → disconnect and reconnect Boba MCP.

---

## 11. MCP Integration Layer

### 11.1 Connection Modes

| Mode | Transport | Use Case | Auth |
|------|-----------|----------|------|
| **stdio** | stdin/stdout pipe | Local dev with `boba proxy` running | Env vars |
| **SSE** | HTTP Server-Sent Events | Remote/headless deployment | Bearer token |

**Connection priority**: stdio first → SSE fallback.

### 11.2 stdio Connection

```
npx -y @tradeboba/cli@latest mcp
  OR
~/.npm/_npx/*/node_modules/.bin/boba mcp
```

### 11.3 SSE Connection

```
Server: https://mcp-skunk.up.railway.app/sse
Auth: Bearer <access_token>

Token sources (priority order):
  1. ~/.config/boba-cli/config.json (from `boba login`)
  2. POST /v2/auth/agent with BOBA_AGENT_ID + BOBA_AGENT_SECRET
```

### 11.4 Tool Discovery

On connect, the client calls `session.list_tools()` which returns all 85+ tool definitions. These are converted to Gemini `FunctionDeclaration` objects with cleaned schemas (uppercase types, Gemini-compatible format).

---

## 12. Data Persistence

### 12.1 Database Configuration

| Property | Value |
|----------|-------|
| Engine | SQLite 3.x |
| Journal mode | WAL (Write-Ahead Logging) |
| File | `signalflow.db` (configurable via `SIGNALFLOW_DB_PATH`) |
| Thread safety | `check_same_thread=False` + WAL |
| Connection | Singleton (`_conn` module-level global) |

### 12.2 Schema (7 Tables)

#### signals
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| market_id | TEXT | Polymarket condition ID |
| market_question | TEXT | Human-readable market question |
| current_price | REAL | Yes token price at detection |
| price_change_pct | REAL | % change over timeframe |
| timeframe_minutes | INTEGER | Detection window |
| category | TEXT | Market category |
| detected_at | TEXT (ISO) | UTC timestamp |

#### analyses
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| signal_id | INTEGER FK → signals | Source signal |
| reasoning | TEXT | Gemini's explanation |
| conviction_score | REAL | 0.0 - 1.0 |
| suggested_direction | TEXT | "long" or "short" |
| suggested_asset | TEXT | e.g., "BTC", "ETH" |
| suggested_size_usd | REAL | Suggested position size |
| risk_notes | TEXT | Includes leverage + hold_hours |
| created_at | TEXT (ISO) | UTC timestamp |

#### positions
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| analysis_id | INTEGER FK → analyses | Source analysis |
| asset | TEXT | Trading pair |
| direction | TEXT | "long" or "short" |
| entry_price | REAL | Actual fill price (post-confirmation) |
| size_usd | REAL | Position size in USD |
| leverage | INTEGER | 1-3x |
| stop_loss | REAL | ATR-based stop price |
| take_profit | REAL | ATR-based target price |
| status | TEXT | "open", "closed", "stopped" |
| pnl | REAL | Realized or unrealized P&L |
| opened_at | TEXT (ISO) | Entry timestamp |
| closed_at | TEXT (ISO) | Exit timestamp (nullable) |

#### position_snapshots
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| position_id | INTEGER FK → positions | Parent position |
| asset | TEXT | Asset symbol |
| current_price | REAL | Price at snapshot time |
| unrealized_pnl | REAL | Unrealized P&L at snapshot |
| timestamp | TEXT (ISO) | Snapshot time |

#### wallet_snapshots
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| balance | REAL | Total wallet balance |
| total_pnl | REAL | Cumulative P&L |
| open_positions | INTEGER | Count of open positions |
| timestamp | TEXT (ISO) | Snapshot time |

#### kol_signals
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| kol_name | TEXT | Wallet owner name |
| wallet_address | TEXT | On-chain address |
| asset | TEXT | Traded asset |
| direction | TEXT | "long" or "short" |
| trade_size_usd | REAL | Trade value |
| detected_at | TEXT (ISO) | Detection time |

#### agent_decisions
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| cycle_id | TEXT | UUID hex (8 chars) |
| signals_detected | INTEGER | Count |
| analyses_produced | INTEGER | Count |
| trades_executed | INTEGER | Count |
| reasoning_summary | TEXT | Human-readable summary |
| timestamp | TEXT (ISO) | Cycle time |

### 12.3 Indexes

```sql
idx_analyses_signal_id           ON analyses(signal_id)
idx_positions_analysis_id        ON positions(analysis_id)
idx_positions_status             ON positions(status)
idx_position_snapshots_position_id ON position_snapshots(position_id)
idx_wallet_snapshots_timestamp   ON wallet_snapshots(timestamp)
idx_signals_detected_at          ON signals(detected_at)
idx_kol_signals_detected_at      ON kol_signals(detected_at)
```

---

## 13. Dashboard & Observability

### 13.1 Pages

| Page | File | Purpose |
|------|------|---------|
| Landing | `00_landing.py` | Project overview, architecture, 5-layer risk showcase, Boba tool inventory |
| Command Center | `01_overview.py` | Pipeline status (5 stages), API connections, key metrics, recent signals + analyses |
| Portfolio | `02_portfolio.py` | Wallet growth line chart, per-position P&L lines, buy/sell annotations, trade table |
| Market Scanner | `03_signals.py` | Signal breakdown by category, price change distribution, signal feed with filters |
| Analytics | `04_analytics.py` | Conviction vs P&L scatter, win rate by bucket, position duration, asset breakdown |
| Whale Intelligence | `05_kol_tracker.py` | KOL signal timeline, top wallets, alignment with agent trades |

### 13.2 Refresh & Theming

- Auto-refresh: every 10 seconds (`DASHBOARD_REFRESH_SECONDS`)
- Theme: Dark mode via `styles/theme.py` (custom CSS + Plotly color scheme)
- Charts: Plotly with interactive zoom, hover tooltips

---

## 14. Deployment Architecture

### 14.1 Docker

```dockerfile
# Multi-stage build
FROM node:20-slim AS node-base     # Boba CLI (npx)
FROM python:3.11-slim AS runtime   # Agent + Dashboard
# Copy node from node-base for npx support
```

### 14.2 docker-compose

```yaml
services:
  agent:
    build: .
    command: python runner.py
    env_file: .env
    volumes:
      - ./signalflow.db:/app/signalflow.db
    restart: unless-stopped

  dashboard:
    build: .
    command: streamlit run dashboard.py --server.port 8501
    ports:
      - "8501:8501"
    volumes:
      - ./signalflow.db:/app/signalflow.db  # shared DB
    restart: unless-stopped
```

### 14.3 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | If USE_VERTEX=false | Google AI API key |
| `GCP_PROJECT` | If USE_VERTEX=true | Vertex AI project ID |
| `GCP_LOCATION` | If USE_VERTEX=true | Vertex AI region |
| `USE_VERTEX` | No (default: true) | Use Vertex AI vs API key |
| `BOBA_API_KEY` | Yes | Boba agent secret |
| `BOBA_AGENT_ID` | For SSE mode | Boba agent identifier |
| `BOBA_AGENT_SECRET` | For SSE mode | Boba agent secret for auth |
| `SIGNALFLOW_DB_PATH` | No (default: signalflow.db) | Database file location |

---

## 15. Configuration Reference

All parameters in `config.py`:

### Signal Detection
| Parameter | Default | Description |
|-----------|---------|-------------|
| `MIN_SIGNAL_PRICE_CHANGE` | 0.08 (8%) | Minimum Polymarket move to trigger signal |
| `SIGNAL_DEDUP_MINUTES` | 15 | Dedup window per market |
| `MARKET_CATEGORIES` | 8 categories | Polymarket search keywords |

### Risk Management
| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_SINGLE_POSITION_PCT` | 0.25 | Max 25% of balance per trade |
| `DEFAULT_STOP_LOSS_PCT` | 0.05 | Fallback SL when ATR unavailable |
| `DEFAULT_TAKE_PROFIT_PCT` | 0.10 | Fallback TP when ATR unavailable |
| `MAX_POSITION_AGE_HOURS` | 4 | Planned hold time default |
| `MIN_FLIP_INTERVAL_MINUTES` | 30 | Cooldown before reversing a position |

### ATR Dynamic Stops
| Parameter | Default | Description |
|-----------|---------|-------------|
| `ATR_PERIOD` | 14 | Candle periods for ATR calculation |
| `ATR_TIMEFRAME` | "1h" | Candle interval |
| `ATR_SL_MULTIPLIER` | 1.5 | SL distance in ATR units |
| `ATR_TP_MULTIPLIER` | 3.0 | TP distance in ATR units (2:1 R:R) |

### Drawdown Circuit Breaker
| Parameter | Default | Description |
|-----------|---------|-------------|
| `DRAWDOWN_WARN_PCT` | 0.10 | Halve sizes at 10% drawdown |
| `DRAWDOWN_HALT_PCT` | 0.20 | Halt at 20% drawdown |
| `DRAWDOWN_COOLDOWN_HOURS` | 6 | Hours before resuming |

### Execution Quality
| Parameter | Default | Description |
|-----------|---------|-------------|
| `MIN_ORDERBOOK_DEPTH_USD` | 500 | Min L2 depth to enter |
| `MAX_SLIPPAGE_PCT` | 0.003 | Max acceptable slippage (0.3%) |

### Agent
| Parameter | Default | Description |
|-----------|---------|-------------|
| `GEMINI_MODEL` | "gemini-2.5-flash" | AI model |
| `CONVICTION_THRESHOLD` | 0.75 | Min conviction to trade |

### Trigger Intervals
| Parameter | Default | Description |
|-----------|---------|-------------|
| `POLYMARKET_TRIGGER_INTERVAL` | 45s | Prediction market scan |
| `KOL_TRIGGER_INTERVAL` | 60s | Whale trade check |
| `FUNDING_TRIGGER_INTERVAL` | 90s | Funding rate check |
| `TOKEN_DISCOVERY_INTERVAL` | 120s | Trending token scan |
| `CROSS_CHAIN_INTERVAL` | 180s | Cross-chain price check |
| `PORTFOLIO_TRIGGER_INTERVAL` | 300s | Wallet sync |

### KOL Tracking
| Parameter | Default | Description |
|-----------|---------|-------------|
| `KOL_MIN_TRADE_USD` | 500 | Min trade size to track |
| `KOL_SIGNAL_BOOST` | 0.10 | Conviction boost on alignment |
| `KOL_DEDUP_MINUTES` | 30 | Dedup window per wallet |

### Portfolio
| Parameter | Default | Description |
|-----------|---------|-------------|
| `PAPER_WALLET_STARTING_BALANCE` | 100.0 | Initial capital |
| `MAX_PORTFOLIO_EXPOSURE_USD` | 1000 | Max total open exposure |
| `MAX_CONCURRENT_POSITIONS` | 5 | Max simultaneous positions |

---

## 16. API & Tool Inventory

### 16.1 Directly Integrated Boba Tools (22)

| # | Tool | File | Risk Layer | Purpose |
|---|------|------|-----------|---------|
| 1 | `pm_search_markets` | signals.py | — | Search prediction markets by keyword |
| 2 | `pm_get_price_history` | signals.py | — | 24H price chart for change detection |
| 3 | `pm_get_top_holders` | agent.py | — | Whale positioning pre-analysis |
| 4 | `pm_get_comments` | agent.py | — | Community sentiment pre-analysis |
| 5 | `hl_get_asset` | agent.py | — | Current Hyperliquid price |
| 6 | `hl_get_markets` | agent.py | — | Market search fallback |
| 7 | `hl_get_history` | risk.py | **Layer 4** | OHLCV candles for ATR computation |
| 8 | `hl_get_orderbook` | risk.py | **Layer 3** | L2 depth for liquidity gate |
| 9 | `hl_get_fills` | risk.py | **Layer 5** | Fill confirmation + slippage |
| 10 | `hl_place_order` | agent.py | — | Market/stop/TP order placement |
| 11 | `hl_update_leverage` | agent.py | — | Set leverage before trade |
| 12 | `hl_close_position` | agent.py | — | Atomic position close (all exits) |
| 13 | `hl_get_predicted_funding` | triggers.py | — | Funding rate spike detection |
| 14 | `get_kol_swaps` | kol_tracker.py | — | Whale trade monitoring |
| 15 | `search_tokens` | triggers.py | — | Trending token discovery |
| 16 | `get_brewing_tokens` | triggers.py | — | Launchpad token scanning |
| 17 | `get_token_price` | triggers.py | — | Cross-chain price comparison |
| 18 | `get_token_info` | agent.py | — | Token fundamentals enrichment |
| 19 | `audit_token` | agent.py | — | Security audit pre-trade |
| 20 | `get_portfolio` | triggers.py | — | Real wallet sync |

### 16.2 Available via Gemini (All 85)

During the analysis phase, Gemini receives all 85 Boba tools as callable functions. The AI can autonomously decide to call additional tools beyond the 22 directly integrated ones.

### 16.3 Tool Categories (Full Boba Inventory)

| Category | Count | Examples |
|----------|-------|---------|
| Hyperliquid | 11 | hl_place_order, hl_get_history, hl_get_orderbook |
| Polymarket | 16 | pm_search_markets, pm_get_market_detail, pm_trade |
| Tracking | 11 | get_kol_swaps, add_wallet_to_tracker, get_user_swaps |
| Analytics | 8 | get_wallet_stats, search_wallets, get_holders |
| Discovery | 7 | search_tokens, get_token_chart, get_token_categories |
| Security | 3 | audit_token, audit_tokens_batch, is_token_verified |
| Orders | 5 | create_limit_order, cancel_limit_order |
| DCA | 3 | create_dca_order, manage_dca_order |
| TWAP | 3 | create_twap_order, manage_twap_order |
| Portfolio | 5 | get_portfolio, get_pnl_chart, get_trade_history |
| Trading | 1 | execute_trade (spot) |
| Token Launch | 5 | launch_token, claim_fees |
| Helper | 3 | convert_amount, get_chain_info |
| Billing | 3 | get_credit_balance, topup_credits |

---

## 17. Error Handling & Resilience

### 17.1 Boba MCP Connection

| Scenario | Behavior |
|----------|----------|
| Initial connection fails | Retry up to 5 times with linear backoff (10s, 20s, 30s, 40s, 50s) |
| stdio fails | Automatic fallback to SSE mode |
| Mid-session disconnect | After 10 consecutive agent errors → disconnect + reconnect |
| Tool call fails | Returns error string to Gemini; Gemini can retry or adapt |

### 17.2 Gemini AI

| Scenario | Behavior |
|----------|----------|
| API timeout (>45s) | Return partial results collected so far |
| Invalid JSON response | `_extract_json()` attempts brace-matching extraction; skip if unparseable |
| Tool loop exhaustion (>10 rounds) | Return whatever text Gemini has produced |
| Model error | Log exception, skip signal, continue to next |

### 17.3 Trigger Tasks

| Scenario | Behavior |
|----------|----------|
| Single trigger error | Exponential backoff: `interval × 2^errors`, capped at 600s |
| Trigger recovery | Reset error counter on first success |
| All triggers failing | Agent loop idle (no events), triggers independently retry |

### 17.4 Trade Execution

| Scenario | Behavior |
|----------|----------|
| Direct execution fails | Fallback to Gemini tool loop |
| Both paths fail | Log error, skip trade, no position opened |
| Fill confirmation fails | Proceed with expected price (best effort) |
| SL/TP order placement fails | Position opens but has no exchange-side protection (DB SL/TP still enforced) |

---

## 18. Performance Characteristics

### 18.1 Latency

| Operation | Typical Latency |
|-----------|----------------|
| Signal detection (1 category) | 1-3s |
| Full scan (8 categories) | 8-15s |
| Gemini analysis (with tools) | 5-30s |
| Trade execution (3 orders) | 2-5s |
| Position management cycle | 1-3s per position |
| ATR computation | 1-2s |
| Orderbook check | 0.5-1s |
| Fill confirmation | 0.5-1s |

### 18.2 Throughput

| Metric | Value |
|--------|-------|
| Events per hour | ~80-120 (varies by market activity) |
| Trades per hour | 0-3 (gated by conviction threshold) |
| Gemini calls per hour | ~20-40 (analysis + exit decisions) |
| DB writes per hour | ~200-400 (snapshots + events) |

### 18.3 Resource Usage

| Resource | Usage |
|----------|-------|
| Memory | ~50-100MB (Python + Boba MCP child process) |
| CPU | Low (mostly I/O-bound, waiting on API calls) |
| Disk | SQLite grows ~1-5MB/day |
| Network | ~1000-3000 Boba tool calls/day |

---

## 19. Security Considerations

### 19.1 Secrets Management

| Secret | Storage | Access |
|--------|---------|--------|
| GEMINI_API_KEY | `.env` file | Python dotenv |
| BOBA_API_KEY | `.env` file | Python dotenv |
| BOBA_AGENT_ID | `.env` file | Python dotenv |
| BOBA_AGENT_SECRET | `.env` file | Python dotenv |
| GCP credentials | ADC (Application Default Credentials) | google-auth |

### 19.2 Data Safety

- **No real funds at risk** — paper trading only ($100 virtual wallet)
- **Database is local** — SQLite file on disk, not exposed to network
- **No PII stored** — KOL wallet addresses are public on-chain data
- **Token audit before every trade** — `audit_token` rejects high-risk/scam tokens

### 19.3 LLM Safety

- **Gemini cannot override risk gates** — risk.py is pure Python, not in the tool loop
- **Gemini cannot execute arbitrary code** — only Boba MCP tools are callable
- **JSON output is validated** — `_extract_json()` with brace-matching, not `eval()`

---

## 20. Known Limitations & Roadmap

### 20.1 Current Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| Peak balance resets on restart | Drawdown breaker loses memory | Could persist to DB |
| No volatility-normalized sizing | Equal-dollar positions have unequal risk | ATR-based sizing planned |
| No correlation awareness | BTC+ETH+SOL = effectively one position | Portfolio beta tracking planned |
| KOL boost is flat | All wallets weighted equally | wallet scoring via `get_wallet_stats` planned |
| Polymarket signals can be noisy | Thin markets cause false signals | Volume/spread filter via `pm_get_market_detail` planned |
| Boba proxy needs TTY | Can't run headless without SSE mode | SSE mode available as workaround |

### 20.2 Roadmap

| Priority | Feature | Boba Tools Needed |
|----------|---------|-------------------|
| P1 | Volatility-normalized position sizing (size inversely proportional to ATR) | `hl_get_history` (already integrated) |
| P1 | Polymarket signal quality filter (reject thin/illiquid markets) | `pm_get_market_detail`, `pm_get_token_data` |
| P2 | KOL wallet performance scoring (weight boost by track record) | `get_wallet_stats`, `search_wallets` |
| P2 | Correlation-aware exposure limits | Custom (rolling correlation from candles) |
| P2 | Transaction cost model (fees + funding + slippage) | `hl_get_fills` (integrated), custom accounting |
| P3 | Market regime detection (trending vs mean-reverting) | `hl_get_history` + custom indicators |
| P3 | TWAP execution for larger positions | `create_twap_order` |
| P3 | Smart money systematic following | `search_wallets`, `add_wallet_to_tracker`, `get_user_swaps` |
| P4 | Deployer front-running defense | `get_deployer_activity` |
| P4 | Spot trading capability | `execute_trade` |

---

*End of document.*
