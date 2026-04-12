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

## v2-fixed-fractional-multi-source (target tag: `v2-fixed-fractional`)

**Date:** 2026-04-11 (in progress)

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
