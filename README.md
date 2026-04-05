# SignalFlow

**AI crypto trading agent that monitors prediction markets, whale wallets, and funding rates to trade perpetual futures — all on a $100 virtual wallet.**

Built with Gemini 2.5 Flash (Vertex AI) + Boba Agents MCP (85 tools) + Hyperliquid + Polymarket

---

## What It Does

Give the agent $100. It scans Polymarket prediction markets, tracks KOL whale wallets, monitors funding rate anomalies, and uses Gemini AI to decide when to open leveraged trades on Hyperliquid. Every position gets a stop-loss, take-profit, trailing stop, and AI-driven exit analysis. The dashboard shows one unified chart of how your $100 is doing — each investment as a colored line, with buy/sell markers.

### Results (overnight run)
- **$100 -> $105.56 (+5.6%)** in 12 hours
- **78% win rate** (7W / 2L out of 9 closed trades)
- 12 total trades across BTC, ETH, SOL

---

## Architecture

```
6 ASYNC TRIGGERS (45s-300s intervals)
  Polymarket | KOL Whales | Funding Rates
  Token Discovery | Cross-Chain | Portfolio Sync
           |
     EVENT BUS (asyncio.Queue)
           |
     AGENT BRAIN
       1. DETECT signal (no AI, pure math)
       2. INTERPRET signal (dip market = bullish, etc.)
       3. ANALYZE with Gemini + 85 Boba tools
       4. RISK CHECK (do we have the money?)
       5. EXECUTE trade via hl_place_order
       6. MANAGE positions:
          - SL/TP every check
          - Trailing stop at 5% profit
          - AI exit analysis every 30 min
          - 6h hard age limit
       7. SNAPSHOT for charts
           |
     STREAMLIT DASHBOARD
       One chart: wallet + each investment's journey
       P&L and win rate displayed prominently
       Trade history with AI reasoning
       KOL whale intelligence
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js (for Boba CLI)
- Google Cloud account with Vertex AI enabled

### 1. Install

```bash
git clone https://github.com/your-org/signalflow.git
cd signalflow
pip install google-genai mcp pydantic streamlit python-dotenv pandas plotly
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Start Boba proxy (Terminal 1)

```bash
npx -y @tradeboba/cli@latest login
npx -y @tradeboba/cli@latest proxy --port 3456
```

### 4. Run agent (Terminal 2)

```bash
python runner.py
```

### 5. Run dashboard (Terminal 3)

```bash
streamlit run dashboard.py
```

Or use the one-command launcher:

```bash
./run.sh
```

### Docker

```bash
docker-compose up --build -d
# Dashboard at http://localhost:8501
# Logs: docker-compose logs -f agent
```

---

## How It Trades

### Signal Sources
| Source | Interval | What It Looks For |
|--------|----------|-------------------|
| Polymarket | 45s | 3%+ moves on crypto prediction markets |
| KOL Whales | 60s | $100+ trades from tracked wallets (429 KOLs) |
| Funding Rates | 90s | Hyperliquid vs Binance rate divergence |
| Token Discovery | 120s | Tokens up 50%+ in 24h with $100k+ volume |
| Cross-Chain | 180s | ETH price differences across chains |

### Signal Interpretation
The agent understands prediction market semantics:
- "Will BTC dip to $50k?" probability DROPS -> market thinks dip less likely -> **BULLISH**
- "Will BTC reach $80k?" probability RISES -> market thinks rally likely -> **BULLISH**

### Position Management
| Layer | Trigger | Action |
|-------|---------|--------|
| Stop-loss | Price hits SL (4% adverse) | Instant close |
| Take-profit | Price hits TP (10% favorable) | Instant close |
| Trailing stop | PnL > 5% | Move SL to break-even |
| AI exit analysis | Every 30 min after 1 hour | Gemini evaluates: hold or close? |
| Position flip | Better opportunity opposite direction | Close old, open new |
| Hard age limit | 6 hours | Safety net close |

### Risk Management
Only real constraints:
- Can't spend more margin than the wallet has
- Can't have contradictory positions (long + short same asset)
- Single trade max 50% of balance
- Everything else: agent decides

---

## Project Structure

```
signalflow/
  runner.py          Entry point — event loop with Boba retry/reconnect
  agent.py           Core brain — analyze, execute, manage, AI exit analysis
  risk.py            Wallet-based risk (margin check, no artificial limits)
  signals.py         Polymarket signal detection + dead market filter
  kol_tracker.py     KOL whale tracking (429 wallets via Boba)
  triggers.py        6 async triggers with exponential backoff
  event_bus.py       asyncio.Queue connecting triggers to agent
  mcp_client.py      Boba MCP connection wrapper
  config.py          All parameters in one place
  models.py          Pydantic data models
  db.py              SQLite persistence (7 tables, indexed)
  dashboard.py       Streamlit multi-page app
  pages/
    01_overview.py   Command center — pipeline + metrics
    02_portfolio.py  THE chart — wallet + per-investment lines + buy/sell markers
    03_signals.py    Market scanner with filtering
    04_analytics.py  Agent performance — conviction vs PnL
    05_kol_tracker.py  Whale intelligence
  styles/
    theme.py         Dark theme + Plotly defaults
  Dockerfile         Multi-stage: Node.js + Python
  docker-compose.yml Agent + dashboard services
  run.sh             One-command launcher
```

---

## Boba MCP Tools Used (20+)

| Tool | Purpose |
|------|---------|
| `pm_search_markets` | Find prediction markets by category |
| `pm_get_price_history` | Detect price movements |
| `pm_get_top_holders` | Whale positioning |
| `pm_get_comments` | Community sentiment |
| `hl_get_asset` | Current Hyperliquid prices |
| `hl_get_markets` | Market search |
| `hl_place_order` | Execute trades + SL/TP orders |
| `hl_update_leverage` | Set leverage |
| `hl_get_predicted_funding` | Funding rate data |
| `get_kol_swaps` | KOL whale trades (429 wallets) |
| `get_kol_wallets` | KOL wallet list |
| `search_tokens` | Trending token discovery |
| `get_brewing_tokens` | Launchpad tokens |
| `get_token_price` | Cross-chain price comparison |
| `get_token_info` | Token fundamentals |
| `audit_token` | Security audit before trading |
| `get_portfolio` | Real wallet state |

All 85 Boba tools are also exposed to Gemini during analysis for autonomous tool use.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Engine | Gemini 2.5 Flash via Google Vertex AI |
| Trading MCP | Boba Agents (85 tools, 9 chains) |
| Perps Exchange | Hyperliquid |
| Prediction Markets | Polymarket |
| Event System | asyncio.Queue + 6 async triggers |
| Database | SQLite (WAL mode, 7 tables, indexed) |
| Dashboard | Streamlit + Plotly |
| Data Models | Pydantic v2 |
| Deployment | Docker + docker-compose |

---

## License

MIT
