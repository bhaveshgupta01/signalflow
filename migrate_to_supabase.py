"""One-time migration: SQLite → Supabase.

Usage:
    SUPABASE_URL=https://xxx.supabase.co SUPABASE_SERVICE_KEY=xxx python migrate_to_supabase.py
"""

import os
import sqlite3
from supabase import create_client

DB_PATH = os.getenv("SIGNALFLOW_DB_PATH", "signalflow.db")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

BATCH_SIZE = 500

# Tables in FK-safe order (parents first)
TABLES = [
    "signals",
    "kol_signals",
    "wallet_snapshots",
    "agent_decisions",
    "analyses",
    "positions",
    "position_snapshots",
]


def migrate():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    for table in TABLES:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  {table}: 0 rows (skipped)")
            continue

        # Convert sqlite3.Row to dicts, drop 'id' so Supabase auto-generates
        records = []
        for r in rows:
            d = dict(r)
            d.pop("id", None)
            records.append(d)

        # Batch insert
        inserted = 0
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i : i + BATCH_SIZE]
            client.table(table).insert(batch).execute()
            inserted += len(batch)

        print(f"  {table}: {inserted} rows migrated")

    conn.close()
    print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
