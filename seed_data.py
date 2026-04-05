"""Seed the SignalFlow database with realistic demo data.

Generates signals, analyses, positions (some open, some closed),
wallet snapshots, position snapshots, KOL signals, and agent decisions
so the dashboard has meaningful data to display immediately.

Run:  python seed_data.py
"""

import sys
import os
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import (
    init_db, save_signal, save_analysis, save_position, update_position,
    save_wallet_snapshot, save_position_snapshot, save_kol_signal, save_decision,
)
from models import (
    Signal, Analysis, Position, WalletSnapshot, PositionSnapshot,
    KolSignal, AgentDecision, Direction, PositionStatus,
)
from config import PAPER_WALLET_STARTING_BALANCE


def seed() -> None:
    init_db()

    now = datetime.utcnow()
    balance = PAPER_WALLET_STARTING_BALANCE
    total_pnl = 0.0

    assets = ["BTC", "ETH", "SOL", "DOGE", "ARB"]
    categories = ["bitcoin", "ethereum", "defi", "crypto", "regulation"]
    kol_names = ["CryptoWhale42", "DegenTrader", "SolMaxi", "ETHBull", "FundingBot"]
    wallets = [
        "0x1a2b3c4d5e6f7890abcdef1234567890abcdef12",
        "0xdeadbeef12345678901234567890123456789012",
        "0xcafebabe12345678901234567890123456789012",
    ]

    # Generate 24 hours of data, one event roughly every 30 min
    num_events = 48
    positions_created = []

    for i in range(num_events):
        ts = now - timedelta(hours=24) + timedelta(minutes=i * 30 + random.randint(-5, 5))
        asset = random.choice(assets)
        category = random.choice(categories)

        # ── Signal ──
        price_change = random.uniform(-0.15, 0.15)
        signal = Signal(
            market_id=f"demo_{asset.lower()}_{i:04d}",
            market_question=f"Will {asset} {'rise above' if price_change > 0 else 'drop below'} ${random.randint(1000, 70000)} by {(ts + timedelta(days=random.randint(1, 7))).strftime('%b %d')}?",
            current_price=round(random.uniform(0.1, 0.9), 3),
            price_change_pct=price_change,
            timeframe_minutes=30,
            category=category,
            detected_at=ts,
        )
        signal = save_signal(signal)

        # ── Analysis (70% of signals get analyzed) ──
        if random.random() < 0.7:
            conviction = round(random.uniform(0.3, 0.95), 2)
            direction = Direction.LONG if price_change > 0 else Direction.SHORT
            analysis = Analysis(
                signal_id=signal.id or 0,
                reasoning=f"Polymarket shows {abs(price_change)*100:.1f}% move on {asset}. "
                          f"{'Bullish' if direction == Direction.LONG else 'Bearish'} sentiment confirmed by "
                          f"{'whale accumulation' if random.random() > 0.5 else 'funding rate divergence'}. "
                          f"Conviction: {conviction:.0%}.",
                conviction_score=conviction,
                suggested_direction=direction,
                suggested_asset=asset,
                suggested_size_usd=round(random.uniform(50, 150), 0),
                risk_notes=random.choice([
                    "Moderate volatility expected",
                    "Watch for reversal at key support",
                    "Low liquidity risk",
                    "Funding rate favourable",
                    "Event catalyst approaching",
                ]),
                created_at=ts + timedelta(seconds=random.randint(5, 30)),
            )
            analysis = save_analysis(analysis)

            # ── Position (40% of high-conviction analyses become trades) ──
            if conviction >= 0.65 and random.random() < 0.4 and len([p for p in positions_created if p["status"] == "open"]) < 3:
                prices = {"BTC": 67000, "ETH": 2050, "SOL": 140, "DOGE": 0.15, "ARB": 1.2}
                entry = prices.get(asset, 100) * (1 + random.uniform(-0.02, 0.02))
                size = round(conviction * random.uniform(50, 120), 0)
                leverage = random.choice([2, 3])
                sl_pct = 0.05
                tp_pct = 0.15

                if direction == Direction.LONG:
                    sl = round(entry * (1 - sl_pct), 2)
                    tp = round(entry * (1 + tp_pct), 2)
                else:
                    sl = round(entry * (1 + sl_pct), 2)
                    tp = round(entry * (1 - tp_pct), 2)

                position = Position(
                    analysis_id=analysis.id or 0,
                    asset=asset,
                    direction=direction,
                    entry_price=entry,
                    size_usd=size,
                    leverage=leverage,
                    stop_loss=sl,
                    take_profit=tp,
                    opened_at=ts + timedelta(seconds=random.randint(30, 60)),
                )
                position = save_position(position)
                pos_info = {"id": position.id, "asset": asset, "direction": direction,
                            "entry": entry, "size": size, "leverage": leverage,
                            "sl": sl, "tp": tp, "status": "open", "opened_at": position.opened_at}
                positions_created.append(pos_info)

                # ── Simulate position lifecycle ──
                # Generate snapshots and maybe close it
                close_chance = random.random()
                num_snapshots = random.randint(3, 12)
                final_pnl = 0.0

                for s in range(num_snapshots):
                    snap_ts = position.opened_at + timedelta(minutes=(s + 1) * random.randint(10, 30))
                    if snap_ts > now:
                        break
                    price_drift = random.uniform(-0.08, 0.12)  # slight upward bias
                    cur_price = entry * (1 + price_drift)

                    if direction == Direction.LONG:
                        pnl = (cur_price - entry) / entry * size * leverage
                    else:
                        pnl = (entry - cur_price) / entry * size * leverage
                    pnl = round(pnl, 2)
                    final_pnl = pnl

                    save_position_snapshot(PositionSnapshot(
                        position_id=position.id or 0,
                        asset=asset,
                        current_price=round(cur_price, 2),
                        unrealized_pnl=pnl,
                        timestamp=snap_ts,
                    ))

                # Close ~60% of positions
                if close_chance < 0.6 and position.opened_at < now - timedelta(hours=2):
                    close_ts = position.opened_at + timedelta(hours=random.uniform(1, 8))
                    if close_ts > now:
                        close_ts = now - timedelta(minutes=random.randint(5, 60))
                    if final_pnl > 0:
                        status = PositionStatus.CLOSED
                    else:
                        status = PositionStatus.STOPPED
                    update_position(position.id, status=status, pnl=final_pnl, closed_at=close_ts)
                    pos_info["status"] = status.value
                    total_pnl += final_pnl
                else:
                    update_position(position.id, pnl=final_pnl)
                    total_pnl += final_pnl

        # ── KOL Signal (20% of events) ──
        if random.random() < 0.2:
            kol = KolSignal(
                kol_name=random.choice(kol_names),
                wallet_address=random.choice(wallets),
                asset=asset,
                direction=random.choice([Direction.LONG, Direction.SHORT]),
                trade_size_usd=round(random.uniform(15000, 250000), 0),
                detected_at=ts + timedelta(seconds=random.randint(0, 60)),
            )
            save_kol_signal(kol)

        # ── Wallet Snapshot (every event) ──
        balance = PAPER_WALLET_STARTING_BALANCE + total_pnl
        save_wallet_snapshot(WalletSnapshot(
            balance=round(balance, 2),
            total_pnl=round(total_pnl, 2),
            open_positions=len([p for p in positions_created if p["status"] == "open"]),
            timestamp=ts,
        ))

        # ── Agent Decision (every 4th event) ──
        if i % 4 == 0:
            save_decision(AgentDecision(
                cycle_id=f"demo_{i:04d}",
                signals_detected=random.randint(1, 5),
                analyses_produced=random.randint(0, 3),
                trades_executed=random.randint(0, 1),
                reasoning_summary=f"[polymarket_move] Signals: {random.randint(1,5)}, Analyses: {random.randint(0,3)}, Trades: {random.randint(0,1)}",
                timestamp=ts,
            ))

    open_count = len([p for p in positions_created if p["status"] == "open"])
    closed_count = len([p for p in positions_created if p["status"] != "open"])
    print(f"Seeded demo data:")
    print(f"  Signals:            {num_events}")
    print(f"  Positions:          {len(positions_created)} ({open_count} open, {closed_count} closed)")
    print(f"  Wallet balance:     ${balance:.2f}")
    print(f"  Total PnL:          ${total_pnl:+.2f}")
    print(f"  KOL signals, snapshots, decisions also generated")
    print(f"\nStart the dashboard:  python3 -m streamlit run dashboard.py")


if __name__ == "__main__":
    seed()
