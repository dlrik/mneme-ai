#!/usr/bin/env python3
"""migrate_from_memory_core.py — One-time migration of memory_core data into mneme.

Run once:
    python scripts/migrate_from_memory_core.py

Copies data from:
    memory_core/memory/facts.db    → mneme/memory/facts.db
    memory_core/memory/graph.db    → mneme/memory/graph.db
    memory_core/memory/episodes.db → mneme/memory/episodes.db
"""

import sqlite3
from pathlib import Path

SRC = Path.home() / "memory_core" / "memory"
DST = Path(__file__).parent.parent / "mneme" / "memory"

# table → which DB file it's in
TABLE_FILES = {
    "facts": "facts.db",
    "edges": "graph.db",
    "episodes": "episodes.db",
    "episode_events": "episodes.db",
}


def migrate():
    print(f"Source:      {SRC}")
    print(f"Destination: {DST}\n")

    total_migrated = 0

    for table, src_fname in TABLE_FILES.items():
        src_db = SRC / src_fname
        dst_db = DST / src_fname

        if not src_db.exists():
            print(f"  ✗ {table}: source not found at {src_db}")
            continue

        src_con = sqlite3.connect(src_db)
        src_cur = src_con.cursor()
        dst_con = sqlite3.connect(dst_db)
        dst_cur = dst_con.cursor()

        before = dst_cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        rows = src_cur.execute(f"SELECT * FROM {table}").fetchall()

        if rows:
            cols = [r[1] for r in dst_cur.execute(f"PRAGMA table_info({table})").fetchall()]
            placeholders = ",".join(["?"] * len(cols))
            dst_cur.executemany(f"INSERT OR IGNORE INTO {table} VALUES ({placeholders})", rows)

        dst_con.commit()
        after = dst_cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        migrated = after - before
        src_con.close()
        dst_con.close()

        status = "✓" if migrated > 0 else "-"
        print(f"  {status} {table}: {before} → {after} (+{migrated})")
        total_migrated += migrated

    print(f"\nMigration complete. {total_migrated} rows copied.")
    print("Run 'mneme-export' to sync migrated data to your Obsidian vault.")


if __name__ == "__main__":
    migrate()
