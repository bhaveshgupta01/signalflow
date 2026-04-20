# SignalFlow — Technical Guide

A walkthrough of the whole system, written so you can reason about it end to end. Every claim has a `file:line` so you can jump to the code and see it for yourself.

---

## 1. What SignalFlow actually is

An autonomous trading agent. It manages a $100 paper wallet on Hyperliquid perpetuals. It does three things in a loop forever:

1. **Listens** to 6 independent signal sources (Polymarket prediction markets, KOL whale wallets, Hyperliquid funding rates, token discovery, cross-chain arb, portfolio sync)
2. **Thinks** using Gemini 2.5 Flash Lite, which has access to 85+ Boba MCP tools as native function calls
3. **Executes** perpetual trades on Hyperliquid, wraps each trade in a 5-layer risk engine, and manages exits mechanically (ATR-based stops + chandelier trailing)

Event-driven, not tick-driven. Each trigger emits an `Event` onto an `asyncio.Queue`. The agent loop consumes events one at a time.

---

## 2. Code map — what lives where

| File | Lines | Role |
|------|-------|------|
| [runner.py](runner.py) | 144 | Entry point. Initializes DB, Boba client, Gemini client, spawns 6 trigger tasks, runs the event loop |
| [agent.py](agent.py) | ~1000 | The core. `run_cycle()` orchestrates the full pipeline per event |
| [triggers.py](triggers.py) | ~300 | 6 async pollers, each on its own interval. Emit Events to the bus |
| [signals.py](signals.py) | 152 | Polymarket-specific detection: price history diff, dedup, dead-market filter |
| [kol_tracker.py](kol_tracker.py) | 192 | Parse KOL swap data, infer direction, emit whale signals |
| [scoring.py](scoring.py) | 238 | Multi-source edge scoring (v2): funding + PM + KOL + trend → weighted sum |
| [mcp_client.py](mcp_client.py) | 190 | Boba MCP connection. stdio first, SSE fallback. Tool discovery |
| [risk.py](risk.py) | 648 | 5-layer risk engine + ATR + chandelier + fixed-fractional sizing |
| [db.py](db.py) | ~600 | SQLite schema (8 tables), CRUD, WAL mode |
| [config.py](config.py) | 121 | All 30+ tunable parameters in one place |
| [models.py](models.py) | 123 | Pydantic v2 data models (Signal, Analysis, Position, KolSignal, etc.) |
| [event_bus.py](event_bus.py) | 54 | `asyncio.Queue` wrapper with `TriggerType` enum |

---

## 3. Architecture — signal to trade

```
┌─────────────────────────────────────────────────────────────┐
│ 6 TRIGGERS (each its own asyncio task, staggered intervals) │
│                                                              │
│ Polymarket (40s) → detect >4% prob move                      │
│ KOL whales (50s) → detect >$300 KOL trade                    │
│ Funding (75s)    → extreme |rate| or cross-venue divergence  │
│ Token discovery (100s) → >50% 24h gain tokens                │
│ Cross-chain (150s) → ETH price diff across L2s               │
│ Portfolio sync (240s) → reconcile wallet state               │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │   EventBus     │  asyncio.Queue
                    │  (event_bus.py)│
                    └────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ AGENT.run_cycle()  (agent.py:242-327)                        │
│                                                              │
│ 1. Detect  → Signal model from trigger data                  │
│ 2. Analyze → Gemini + Boba tool loop → Analysis (conviction) │
│ 3. KOL boost → +15% conviction if whale agrees               │
│ 4. Risk gate → drawdown, margin, liquidity, asset whitelist  │
│ 5. Size     → fixed-fractional 1.5% wallet risk              │
│ 6. Execute  → leverage, market order, fill confirm, SL, TP   │
│ 7. Persist  → save Position + Signal + Analysis + Attribution│
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ MANAGE OPEN POSITIONS (every cycle)                          │
│                                                              │
│ - Mark to market (hl_get_asset)                              │
│ - Check hard SL / hard TP hits                               │
│ - Update chandelier trailing stop                            │
│ - Close if age > 12h                                         │
└─────────────────────────────────────────────────────────────┘
```

Entry point: [runner.py:138-143](runner.py#L138). Event loop: [runner.py:109-133](runner.py#L109). Cycle: [agent.py:242-327](agent.py#L242).

---

## 4. Configuration

All knobs live in [config.py](config.py). Everything reads from env vars with sensible defaults.

### Credentials
```
GEMINI_API_KEY       # Gemini (either via API key or Vertex)
BOBA_API_KEY         # Boba MCP
BOBA_AGENT_ID        # for SSE auth fallback
BOBA_AGENT_SECRET
GCP_PROJECT          # default: graphical-interface
GCP_LOCATION         # default: us-central1
USE_VERTEX           # true → Vertex AI, false → free API key
```

### Key thresholds
| Parameter | Value | Where |
|-----------|-------|-------|
| `MIN_SIGNAL_PRICE_CHANGE` | 4% | PM move threshold |
| `SIGNAL_DEDUP_MINUTES` | 8 | don't refire same market |
| `KOL_MIN_TRADE_USD` | $300 | whale trade floor |
| `KOL_DEDUP_MINUTES` | 20 | same wallet+asset+side suppression |
| `RISK_PCT_PER_TRADE` | 1.5% | fixed-fractional sizing |
| `ATR_SL_MULTIPLIER` | 1.0 | tight stop |
| `ATR_TP_MULTIPLIER` | 3.0 | 3:1 R:R target |
| `DRAWDOWN_WARN_PCT` | 15% | halve sizes above this |
| `DRAWDOWN_HALT_PCT` | 30% | stop trading for 4h |
| `MAX_CONCURRENT_POSITIONS` | 8 | portfolio cap |
| `MAX_POSITION_AGE_HOURS` | 12 | forced exit |
| `FUNDING_EXTREME_THRESHOLD` | 0.025% | contrarian trigger |
| `CHANDELIER_ACTIVATION_ATR` | 1.5 | trail activates after this much favor |
| `CHANDELIER_ATR_MULT` | 2.0 | trail distance behind extreme |

---

## 5. The Boba MCP client — [mcp_client.py](mcp_client.py)

The one piece of plumbing that makes everything else possible.

### Two transport modes with automatic fallback — [mcp_client.py:87-189](mcp_client.py#L87)

**Stdio** ([mcp_client.py:105-130](mcp_client.py#L105)):
- Spawns `npx -y @tradeboba/cli@latest mcp` as a subprocess
- Passes `BOBA_API_KEY` via env var
- Works locally, fails in headless/containerized deploys because it wants a TTY

**SSE fallback** ([mcp_client.py:132-153](mcp_client.py#L132)):
- Connects to `https://mcp-skunk.up.railway.app/sse`
- Auth:
  1. Try reading cached token from `~/.config/boba-cli/config.json` (macOS: `~/Library/Application Support/boba-cli/config.json`)
  2. If not found, POST `{agentId, secret}` to `https://krakend-skunk.up.railway.app/v2/auth/agent`
  3. Get back `accessToken`, send as `Authorization: Bearer {token}` header

The `connect()` method tries stdio first, and on any exception falls back to SSE. That's what lets SignalFlow deploy without a terminal.

### Tool discovery — [mcp_client.py:155-166](mcp_client.py#L155)

After `session.initialize()`, the client calls `session.list_tools()`. This returns all 85+ Boba tools with their name, description, and `inputSchema`. Stored on the client, exposed via `tools_for_claude` property.

### Schema translation for Gemini — [agent.py:178-239](agent.py#L178)

Boba returns JSON Schema with lowercase types (`"string"`, `"object"`). Gemini's function-calling API wants uppercase (`"STRING"`, `"OBJECT"`). `_clean_schema_for_gemini()` is a recursive walker that:
- Uppercases all types
- Resolves union types like `["string", "null"]` → picks the non-null
- Keeps `properties`, `required`, `items`, `enum` intact

Then `_boba_tools_to_gemini()` wraps each cleaned schema in a `types.FunctionDeclaration` that Gemini can use.

### Tool invocation — [mcp_client.py:174-182](mcp_client.py#L174)

`call_tool(name, arguments)` awaits `session.call_tool()` and joins the text blocks from the MCP response into a single string. The caller parses the string (usually JSON).

### Retry logic — [runner.py:65-83](runner.py#L65)

On startup, `connect_boba_with_retry()` tries up to 5 times with exponential backoff capped at 60s. After 10 consecutive errors during the event loop, it reconnects.

---

## 6. Signal detection layer — the six triggers

All six live in [triggers.py](triggers.py) as async functions launched in parallel at startup ([runner.py:100-106](runner.py#L100)).

### 6.1 Polymarket — [signals.py:28-117](signals.py#L28)

Runs every 40s. For each category in `MARKET_CATEGORIES` (crypto, bitcoin, ethereum, defi, regulation, SEC, ETF, solana):

1. `pm_search_markets({"q": category, "limit": 10})` → top markets
2. For each market, `pm_get_price_history({"market": token_id, "interval": "1d", "fidelity": 24})` → 24h price array
3. Compute `price_change = last / first - 1`

**Filter logic**:
- Reject if `|price_change| < 4%` (noise floor)
- Reject if `yes_price < 8%` or `> 92%` (dead/resolved market)
- Reject if question contains "reach/above/dip/drop" AND prob < 15% (these are mispriced tail bets)
- Dedup via `get_signals_for_market(condition_id, minutes=8)` — skip if fired in last 8 minutes

Passing signals get saved to DB and emitted as `Event(trigger=TriggerType.POLYMARKET_MOVE, data={"signal": signal})`.

### 6.2 KOL whale tracking — [kol_tracker.py:22-76](kol_tracker.py#L22)

Every 50s. Calls `get_kol_swaps({"limit": 30})`. For each swap:

- Extract KOL name + wallet ([kol_tracker.py:41-43](kol_tracker.py#L41))
- Map bought/sold symbols to Hyperliquid-tradable set ([kol_tracker.py:98-133](kol_tracker.py#L98))
- Get trade size from top-level `usd` field
- **Direction inference** ([kol_tracker.py:160-191](kol_tracker.py#L160)): `BUY_WITH_NATIVE` → LONG, `SELL_FOR_NATIVE` → SHORT (this was a v1 bug — always came out LONG. Fixed in v2)

Filter: trade > $300, not a duplicate (same wallet+asset+direction in last 20 min). Emits `KOL_WHALE_TRADE` events.

**Conviction boost**: when a KOL trade aligns with the agent's existing signal direction, [agent.py:269-283](agent.py#L269) boosts conviction by `KOL_SIGNAL_BOOST = 0.15` (+15%).

### 6.3 Funding rates — [triggers.py:76-136](triggers.py#L76)

Every 75s. `hl_get_predicted_funding({})` returns per-asset funding rates for Hyperliquid and Binance. Two trigger conditions:

- **Extreme**: `|hl_rate| > 0.025%` per 8h → contrarian signal (fade the crowded side). Positive funding means longs paying → crowded long → SHORT signal.
- **Divergence**: `|hl_rate - binance_rate| > 0.01%` → cross-venue arb signal.

### 6.4 Token discovery — [triggers.py:139-203](triggers.py#L139)

Every 100s. Uses `search_tokens` (filters: 24h change >50%, volume >$100k) and `get_brewing_tokens` (launchpad tokens >80% to graduation). Currently informational — logged but not auto-traded.

### 6.5 Cross-chain arb — [triggers.py:206-267](triggers.py#L206)

Every 150s. `get_token_price({"tokens": ["native:1", "native:8453", "native:42161"]})` gets ETH price on Ethereum, Base, Arbitrum. If max diff > 0.3%, logs as opportunity. Also informational for now.

### 6.6 Portfolio sync

Every 240s. Reconciles our DB positions with `get_portfolio()` from Boba.

---

## 7. The reasoning layer — Gemini

### Model + client setup — [runner.py:42-62](runner.py#L42)

Model: `gemini-2.5-flash-lite`. Backend toggle: `USE_VERTEX=true` uses Vertex AI (paid, auth via GCP), otherwise free API key.

### System prompt — [agent.py:77-146](agent.py#L77)

Tells Gemini to follow a 4-step reasoning flow:

1. **Context snapshot** — market regime, macro catalysts
2. **Signal quality** — Dog (spot/structure) vs Tail (derivatives/funding) vs Sentiment (PM + holders)
3. **Hypothesis** — one-line thesis, edge type (flow/mean-reversion/narrative/sentiment), edge depth, invalidation level
4. **Decision** — return JSON: `conviction` (0-1), `direction` (long/short), `asset`, `leverage` (1-5), `hold_hours`, `reasoning`, `risk_notes`, `edge_type`, `edge_depth`

### Per-signal analysis — [agent.py:422-537](agent.py#L422)

1. Fetch extra context: `pm_get_top_holders` + `pm_get_comments` for the market ([agent.py:431-448](agent.py#L431))
2. Apply interpretation guardrails ([agent.py:450-486](agent.py#L450)) — "dip" markets going down = bullish, "reach" markets going up = bullish, and ambiguous cases get checked against spot + funding
3. **Learning loop** ([agent.py:385-417](agent.py#L385)): pull historical win rate for this asset+direction over last 7 days, inject into prompt so Gemini can factor in "we've lost on SHORT SOL 4 times in a row, lower conviction or flip"
4. Run tool loop (next section)
5. Parse JSON with `_extract_json()`, clamp leverage with `clamp_leverage(leverage, conviction)`

### The tool loop — [agent.py:842-902](agent.py#L842)

`_run_tool_loop(client, boba, system, user_message, max_rounds=10)`:

```python
# 1. Convert Boba tools to Gemini function declarations
# 2. Send message to Gemini with tools attached
# 3. Loop:
#    a. Gemini responds with either tool_calls or text
#    b. If tool_calls: execute each via boba.call_tool(), append results
#    c. If text: break, return the text
# 4. Hard limit: 10 rounds, 45s total timeout
```

On timeout or max rounds, return partial response. Errors from tool calls come back as `"Error: ..."` strings; Gemini sees them and usually adapts (retries a different tool).

### JSON extraction — [agent.py:909-933](agent.py#L909)

Gemini responses can be wrapped in markdown fences, have preambles, or mix JSON with explanation. `_extract_json()` does three-pass fallback: strip fences → find first balanced `{...}` → regex extraction. Brittle but works.

---

## 8. The 5-layer risk engine — [risk.py](risk.py)

Pure Python. No LLM override possible. Runs in order before every execution.

### Layer 1: Drawdown circuit breaker — [risk.py:169-213](risk.py#L169)

Tracks peak balance in memory. Computes `drawdown = (peak - current) / peak`.

- `<15%`: normal
- `15-30%`: warning — sizes halved downstream in [risk.py:572-579](risk.py#L572)
- `≥30%`: **halt all new trades for 4 hours**

Known limitation: peak is in-memory, resets on restart. Should persist to DB.

### Layer 2: Margin & position limits — [risk.py:477-520](risk.py#L477)

`can_open_position(size, leverage)` checks:
1. Drawdown gate (above)
2. `len(open_positions) < 8`
3. Available margin = balance − used_margin − 10% reserve
4. Anti-flip cooldown: same asset can't flip direction within 10 min

### Layer 3: Orderbook liquidity — [risk.py:218-295](risk.py#L218)

`hl_get_orderbook({"coin": asset})`. Sum top 5 levels on the side we'd hit. Requires `depth_usd ≥ $500`. Estimates slippage as `VWAP vs mid_price`, caps at 5%. For paper trading, warns but doesn't block.

### Layer 4: ATR-based dynamic stops — [risk.py:54-147](risk.py#L54)

`compute_atr(boba, asset)`:
1. `hl_get_history({"coin": asset, "interval": "1h", "limit": 19})` — 14 periods + buffer
2. True Range = `max(high-low, |high-prev_close|, |low-prev_close|)`
3. ATR = average over 14 periods

`compute_stop_take_atr(entry, direction, atr)`:
- SL distance = `max(atr × 1.0, entry × 0.5%)`
- TP distance = `max(atr × 3.0, entry × 1.5%)`
- Fallback if ATR unavailable: fixed 2.5% SL, 7.5% TP

No hard caps on SL/TP distance — they scale with volatility. That's how you get tight stops on BTC and wider stops on DOGE without one-size-fits-all.

### Layer 5: Fill confirmation — [risk.py:300-348](risk.py#L300)

After market order, `hl_get_fills({"coin": asset, "limit": 5})` gets the actual fill. If actual ≠ expected, recalculate SL/TP from actual entry. Log slippage > 5% as warning.

### Fixed-fractional position sizing — [risk.py:536-602](risk.py#L536)

```
risk_dollars  = balance × 1.5%
notional      = (risk_dollars / stop_distance_pct) × leverage
```

This is the v2 change. Now the trader **never loses more than 1.5% of the wallet on a single stop-out**, regardless of the asset or its volatility. Big volatility → wider stop → smaller notional. Small volatility → tighter stop → bigger notional. Same risk either way.

Size is then capped at `MAX_PER_TRADE_PCT × balance × leverage` (30%) and rejected if below $8 (dust filter).

### Chandelier trailing stop — [risk.py:607-647](risk.py#L607)

After entry, track `extreme_price` (high-water for longs, low-water for shorts). Once price has moved `1.5 × ATR` in favor, activate trailing: SL follows `extreme - 2.0 × ATR` for longs. Stop only ratchets toward profit, never loosens.

Stored per-position in the DB's `extreme_price` and `atr_at_entry` columns ([db.py](db.py) positions table).

---

## 9. Execution — [agent.py:542-731](agent.py#L542)

Order of operations for a new trade:

1. **Asset whitelist** — reject if not in `TRADABLE_ASSETS` {BTC, ETH, SOL, DOGE, ARB, AVAX, LINK, SUI, INJ, OP, APT}
2. **Leverage clamp** — `clamp_leverage(leverage, conviction)` caps leverage inversely to conviction
3. **Entry price** — `hl_get_asset(asset)` → current mark
4. **ATR + stops** — `compute_atr()` then `compute_stop_take_atr()`
5. **Size** — `calculate_position_size_v2(stop_distance, leverage)`
6. **Liquidity check** — `check_orderbook_liquidity()` (warn-only for paper)
7. **Set leverage** — `hl_update_leverage({coin, leverage, mode: "cross"})`
8. **Market order** — `hl_place_order({coin, side: "buy"/"sell", size: usd, type: "market"})`
9. **Fill confirm** — `confirm_fill_and_track_slippage()` → if actual ≠ expected, recompute stops from actual
10. **Stop-loss** — `hl_place_order({type: "stop", triggerPrice: sl})`
11. **Take-profit** — `hl_place_order({type: "take_profit", triggerPrice: tp})`
12. **Persist** — save Position, Signal, Analysis, and signal_attribution rows

### Position management — [agent.py:736-837](agent.py#L736)

Every cycle, for each open position:

1. Mark to market → save `position_snapshots` row (drives the per-position PnL chart)
2. Hard SL: for LONG, trigger if `current ≤ stop_loss`; SHORT mirror
3. Hard TP: same logic reversed
4. Update chandelier: push `extreme_price`, call `chandelier_stop()`, update SL if it ratcheted
5. Age limit: if `opened_at > 12h ago`, close immediately

Close via `hl_close_position()` (atomic on Hyperliquid). Status becomes `CLOSED` (profit) or `STOPPED` (loss) for analytics.

---

## 10. Persistence — [db.py](db.py)

SQLite, WAL mode, 8 indexes. Eight tables:

| Table | Key columns | What it stores |
|-------|-------------|----------------|
| `signals` | market_id, price_change_pct | Every detected Polymarket move |
| `analyses` | signal_id, conviction_score | Gemini's output per signal |
| `positions` | analysis_id, entry_price, stop_loss, take_profit, **extreme_price**, **atr_at_entry** | All trades, open and closed |
| `position_snapshots` | position_id, current_price, unrealized_pnl | Per-cycle PnL history (charts) |
| `wallet_snapshots` | balance, total_pnl | Portfolio state over time |
| `kol_signals` | kol_name, asset, direction | Whale trades detected |
| `agent_decisions` | cycle_id, reasoning_summary | One row per agent cycle |
| `signal_attribution` (v2) | position_id, score_funding, score_polymarket, score_kol, score_trend | Which source drove which trade (for learning) |

**v2 additions**: `extreme_price` and `atr_at_entry` on positions (chandelier needs these across cycles). `signal_attribution` table (so you can answer "which signal source actually makes money").

---

## 11. Dashboards

### Streamlit — 6 pages
- `00_landing.py` (25K) — architecture overview, pitch
- `01_overview.py` — live pipeline status, signal feed, AI reasoning
- `02_portfolio.py` — wallet growth, per-position PnL, entries/exits on chart
- `03_signals.py` — signal distribution + feed
- `04_analytics.py` — conviction vs PnL scatter, win rate by asset
- `05_kol_tracker.py` — KOL volume, correlation table, whale feed

### Next.js dashboard — `web/`
TypeScript + Recharts + Tailwind, themed to boba.xyz. Reads from the same SQLite DB. Still being finished.

---

## 12. v1 vs v2 — what changed and why

**v1** (commit `bbc1271`, tagged `v1-baseline-pre-strategy-rewrite`)
- Size scaled with conviction ($30-180 notional)
- Stops capped at 5%/12% even when ATR said otherwise
- AI re-evaluated every position mid-flight; could close early
- R:R came out ~0.29:1. Avg loss $1.32, avg win $0.38. Bleeding by design.
- KOL direction was always LONG (bug)

**v2** (commit `7a160eb`, current)
- **Fixed-fractional sizing** — 1.5% wallet risk per trade, always
- **Mechanical exits only** — no AI override. Stops hit or TP hits or 12h age-out. The AI decides entries, the risk engine owns exits.
- **ATR stops uncapped** — 1.0×ATR tight SL, 3.0×ATR fat TP. Chandelier trails once in profit.
- **Multi-source scoring** — 4 independent edge sources ([scoring.py](scoring.py)): funding ±1.0, PM ±0.6, KOL ±0.6, EMA trend ±0.4. Trade fires when `|sum| ≥ 1.8` (majors) or `≥ 1.5` (alts).
- **KOL direction bug fixed** — BUY_WITH_NATIVE → LONG, SELL_FOR_NATIVE → SHORT
- **Asset whitelist enforced at execute time**
- **Learning loop** — past 7-day win rate for (asset, direction) injected into analysis prompt

See [VERSION_HISTORY.md](VERSION_HISTORY.md) for the rollback anchors.

---

## 13. Running it

### Local dev
```bash
# Terminal 1 — Boba proxy (if using stdio)
npx -y @tradeboba/cli@latest login --agent-id "..." --secret "..."
npx -y @tradeboba/cli@latest proxy --port 3456

# Terminal 2 — the agent
python3 runner.py

# Terminal 3 — dashboard
streamlit run dashboard.py
# or
cd web && npm run dev
```

### Docker
```bash
docker-compose up --build -d
# Agent :8000, Streamlit :8501, Next.js :3000
```

### Env vars
See [config.py](config.py) or section 4 above.

---

## 14. Known issues + TODO

From [HANDOVER.md:316-332](HANDOVER.md#L316):

1. **Boba stdio needs a TTY** — breaks headless. SSE fallback handles this but is less reliable. Not a SignalFlow bug, a Boba CLI quirk.
2. **Per-position charts empty at first** — `position_snapshots` only starts populating once trades run. Fine after a cycle or two.
3. **Peak balance in-memory** — drawdown breaker resets on restart. Should be persisted.

### Backlog (not blockers)
- Volatility-normalized sizing (inverse to ATR across portfolio)
- Correlation-aware position limits (don't stack 3 correlated longs)
- KOL wallet scoring — weight each KOL by their historical win rate instead of a flat 15% boost
- Market regime detection — ATR ratio + trend strength → adapt thresholds
- Execution: TWAP/DCA for larger orders
- Fee + funding cost model in PnL calculations
- Polymarket spread/volume quality filter

---

## 15. End-to-end example

A Polymarket signal lifecycle, start to finish:

1. **t=0**: Polymarket trigger fires (40s interval). "Will BTC dip below $60k?" probability drops 5%.
2. **signals.py**: Passes 4% threshold, not in dedup window, not a mispriced tail. Saved to `signals` table. Event emitted.
3. **agent.run_cycle()** picks up the event.
4. **_analyze_signal**: Fetches `pm_get_top_holders` + `pm_get_comments`. Builds learning context (past BTC LONG trades in 7 days: 3-1, +$4.20 total PnL). Applies interpretation hint: "dip market" prob falling = bullish.
5. **Gemini tool loop**: Calls `hl_get_asset("BTC")` → $63,950. Calls `hl_get_history("BTC", "1h")` → candles. Calls `hl_get_predicted_funding` → BTC funding normal.
6. **Gemini returns**: `{"conviction": 0.72, "direction": "long", "asset": "BTC", "leverage": 3, ...}`
7. **KOL boost**: A whale bought BTC 2 min ago → conviction 0.72 → 0.85.
8. **Risk gates**: drawdown 3% (OK). 2 positions open (OK). BTC book depth $50k (OK).
9. **ATR**: $1,200. SL = $62,800 (1.9%), TP = $67,600 (5.6%). R:R 3:1.
10. **Size**: `($100 × 1.5%) / 0.019 × 3 = $236` notional.
11. **Execute**: `hl_update_leverage(BTC, 3, cross)` → `hl_place_order(BTC, buy, $236, market)` → filled @ $63,950 → `hl_place_order(stop, $62,800)` → `hl_place_order(take_profit, $67,600)`.
12. **Persist**: Position saved. extreme_price = $63,950. atr_at_entry = $1,200.
13. **Every cycle after**: mark-to-market, update extreme_price, ratchet chandelier SL upward once price moves past $65,750.
14. **Close**: Price hits $67,600 → `hl_close_position(BTC)` → status = CLOSED, pnl = +$9.44.
15. **Learning**: Next BTC LONG signal will include this trade in the 7-day context.

---

That's the whole system. If you're coming back to this later, start at [agent.py:242](agent.py#L242) and follow the `run_cycle()` function — every section above branches off from there.
