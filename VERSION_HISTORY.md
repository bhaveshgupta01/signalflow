# SignalFlow Strategy Version History

Each entry records a major strategy/risk change so we can roll back if a new version underperforms. Use the git tag in the header to checkout that version.

---

## v1-baseline-pre-strategy-rewrite (tag: `v1-baseline-pre-strategy-rewrite` @ commit `bbc1271`)

**Date frozen:** 2026-04-11
**Wallet at freeze:** $82.74 (-17.26 from $100 over 8 days, 102W/31L closed)

**Strategy summary:**
- Polymarket-driven signals only (Polymarket primary, KOL boost, no funding direction)
- Conviction-scaled sizing $30-180 notional (LLM picks size)
- ATR×1.5 SL, ATR×3 TP (capped at 5%/12%)
- Break-even trailing stop after +5% profit
- AI-driven exit re-evaluation at planned hold time
- BTC/ETH/SOL universe, no asset whitelist

**Known issues that motivated v2:**
- Avg loss $1.32 vs avg win $0.38 (R:R 0.29:1)
- 31 stop-outs cost $40.92 (entire P&L hole)
- KOL signals 100% LONG due to `_infer_direction` bug (547 longs / 0 shorts)
- BTC -$11.82, ETH -$11.31 net (only SOL profitable at +$6.46)
- 2x leverage trades worst (-$10.47 over 25 trades) — clamp didn't shrink size
- Funding rate trigger only fires on cross-venue arb diff, not on extremes
- Garbage `suggested_asset` like "CRYPTO_HACK_EVENT" reaching execution
- AI exit loop systematically closes winners early

**To roll back:**
```
git checkout v1-baseline-pre-strategy-rewrite
```

---

## v2-fixed-fractional (tag: `v2-fixed-fractional` @ commit `7a160eb`)

**Date frozen:** 2026-04-11
**Wallet at commit:** $82.74 (rolled forward from v1)

**Strategy summary:**
- **Sizing:** Fixed-fractional 1.5% wallet risk per trade. `size = (risk$ / stop_distance) × leverage`. No more conviction → notional table.
- **Exits:** Mechanical only — hard SL, hard TP (ATR×1 / ATR×3), Chandelier trailing stop (high − 2×ATR after price moves 1.5×ATR in favour), 12h hard max age. **AI exit loop deleted.**
- **Edge stack:** 4-source weighted score in `scoring.py`:
  - Funding extremes (weight 1.0)
  - Polymarket shift (0.6)
  - KOL whale flow (0.6, after bug fix)
  - EMA8/21 trend alignment (0.4)
  - Trade fires when |sum| ≥ 1.5 (alts) or ≥ 1.8 (BTC/ETH)
- **Funding edge:** `hl_get_predicted_funding` polled every 75s; |rate| > 0.025%/8h fires standalone trigger AND adds to score for any other signal on the same asset.
- **Universe:** BTC, ETH, SOL, DOGE, ARB, AVAX, LINK, SUI, INJ, OP, APT — enforced whitelist before execution.
- **Bug fixes:**
  - `kol_tracker._infer_direction`: SELL → SHORT (was always LONG)
  - `clamp_leverage` ↔ `calculate_position_size`: leverage and size now scale together
  - Asset whitelist gate in `_execute_trade`
- **Telemetry:** New `signal_attribution` table records score breakdown per position so we can measure which edge actually pays.

**Decisions / open questions:**
- Risk per trade: 1.5%
- Funding role: standalone + confirming weight
- Exit logic: Chandelier, no AI

**To roll back to v1:**
```
git checkout v1-baseline-pre-strategy-rewrite
```

---

## v2.1-tuned (target tag: `v2.1-tuned`)

**Date:** 2026-04-16
**Wallet at freeze:** $82.79 (v2 was running v1 code in memory — see below)

**Context — what actually happened between v2 commit (Apr 11) and Apr 16:**
- The agent process kept running with v1 bytecode in memory. All 99 "v2" trades used v1 logic (5%/12% SL/TP caps, no chandelier, no attribution). `extreme_price` and `atr_at_entry` populated 0/99 times; `signal_attribution` had 0 rows.
- v2 still beat v1 (net +$1.72 vs −$17.89) because the kol_tracker bugfix and the tighter stops helped, but the core v2 machinery never ran.
- Commit `6711166` deleted the LLM fallback path that was masking execution failures and restarted the agent with fresh v2 code.

**v2.1 changes (in progress):**
- Lower score thresholds to reality: alts 0.8, majors 1.1 (were 1.5/1.8 and unreachable because funding+KOL typically contribute 0).
- BTC/ETH PM gate: Polymarket signals on majors are rejected unless funding is already extreme (|HL rate| > 0.025%/8h). Evidence: BTC+ETH Polymarket-driven trades lost ~$23 net across both versions.
- Deterministic learning cap: if last 5+ trades on same asset+direction netted ≤ −$0.50, conviction is hard-capped at 0.30 regardless of what the LLM says. If they netted ≥ +$1.00, conviction gets +0.10.

**Decisions / open questions:**
- KOL pipeline returning 0 signals since Apr 12 — need to investigate `get_kol_swaps` return shape or lower `KOL_MIN_TRADE_USD`.
- Funding often below extreme threshold — may need a softer "warm" band (|rate| > 0.01%/8h = weak funding score ±0.3).

**To roll back to v2:**
```
git checkout v2-fixed-fractional
```

---

## v2.2-smart-money-and-oi-flow (target tag: `v2.2`)

**Date:** 2026-04-16
**Motivation:** The original KOL pipeline (`get_kol_swaps`) had two known problems: (1) every Solana memecoin trade was relabelled as "SOL" so we lost real asset info, (2) the Boba feed went cold on Apr 10 and has returned `{"count":0,"swaps":[]}` ever since. The whale dashboard was effectively frozen.

**What shipped:**

1. **Rewrote `kol_tracker.py`** to use `search_wallets` + `get_wallet_swaps`:
   - Discovery every 60 min across Solana, Ethereum, Base (top wallets by PnL / win rate / volume, with bot-score filter).
   - Poll each discovered wallet via `get_wallet_swaps` and preserve the real traded asset. Wrapped assets (WETH/WBTC/WSOL) normalised to their underlying.
   - Proper BUY → long, SELL → short direction.
   - Filters to assets in `TRADABLE_ASSETS` — ignores memecoin noise.

2. **Added `hl_whale_trigger` using OI deltas** (`triggers.py`):
   - Every 3 min snapshots Open Interest per major via `hl_get_markets`.
   - Compares against prior snapshot, emits `HL_WHALE_FLOW` when |ΔOI| ≥ 5%.
   - Interprets: OI↑ + price↑ → longs opening (bullish); OI↑ + price↓ → shorts opening (bearish); OI↓ + price↑ → shorts covering (bullish); OI↓ + price↓ → longs capitulating (bearish).
   - Event flows through `handle_event` → `evaluate_trade` → `_execute_trade` with a synthetic KOL-slot score weighted by ΔOI magnitude.

3. **New `HL_WHALE_FLOW` event type** (`event_bus.py`) and handler in `agent.handle_event` that fetches funding, scores, and fires a trade if the composite score passes.

**Not delivered (server-side block):**
- `search_wallets` returns `count:0` across Solana/Ethereum/Base. Boba's wallet analytics DB is empty for our account. Pipeline is written correctly; if they populate it, signals will start flowing without code changes.
- `hl_get_history(type="trades")` doesn't exist (only `candles`/`funding`). That's why the OI-delta approach replaced the trade-tape approach mid-session.
- `get_holders` also returns `count:0`. Wallet analytics are collectively dead on Boba right now.

**Why the OI-delta approach is actually stronger:**
OI measures *net committed capital*, not just churn. A $100M trade that opens 1 long and closes 1 short has zero OI change — both cancel. But a $100M net OI increase means $100M of new longs or shorts actually took risk. That's the real institutional signal, cleaner than trade-tape data would have been.

**Files touched:**
- `kol_tracker.py` — full rewrite (smart money pipeline)
- `triggers.py` — new `hl_whale_trigger` with OI-delta logic
- `event_bus.py` — new `HL_WHALE_FLOW` trigger type
- `agent.py` — new `HL_WHALE_FLOW` branch in `handle_event`
- `runner.py` — register the new trigger
- `config.py` — HL whale thresholds (min fill, interval, imbalance ratio)

**To roll back to v2.1.2:**
```
git checkout v2.1.2-stdio-first
```

---

## v2.1.3-sse-attempt (reverted, kept in history)

**Date:** 2026-04-16
**Status:** Attempted and rolled back in the same session. The stdio+proxy setup is kept.

**What was tried:** Flip `mcp_client.py` `connect()` to try SSE first, then fall back to stdio. Strip the proxy startup from `run.sh`. Goal was to get rid of the `script -q /dev/null` TTY workaround and the 5-99% CPU cost of the local proxy daemon.

**Why it failed:** The SSE path needs a valid Boba access token. We have two sources:
- `~/Library/Application Support/boba-cli/config.json` — **has no `accessToken` field**, only metadata (`accessTokenExpiresAt`, `agentId`, etc.). The Explore agent mis-read this file.
- `POST https://krakend-skunk.up.railway.app/v2/auth/agent` with `BOBA_AGENT_ID` + `BOBA_AGENT_SECRET` — **returns HTTP 404**. The endpoint either moved or was never live.

With no token, `_connect_sse()` raises `RuntimeError("No Boba access token")`. Stdio fallback then also failed because `boba mcp` requires the proxy to be running (which we had just removed from `run.sh`). Agent couldn't connect at all.

**Lesson:** The `boba proxy` daemon isn't just operational overhead — it's the only thing that can auth against Boba's cloud in this environment. The proxy holds the refresh-token state and serves auth to `boba mcp`. Without an interactive `boba login` (device-code flow that populates the token in `config.json`), SSE is not usable from this machine.

**Revisit this when:**
- Boba publishes a working `/v2/auth/agent` endpoint with documented URL, or
- We add a "run `boba login` first, then SSE works" flow to the launcher, or
- We move to a deployment target where the local proxy CAN run as a daemon (a VM, not Mac).

**For now:** stdio + local proxy + `script -q /dev/null` TTY wrapper remains the working transport.
