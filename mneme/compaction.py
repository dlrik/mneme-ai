"""compaction.py — Distill → merge → archive pipeline.
Keeps memory lean. Runs on a schedule or on-demand.
"""
import fact_store, entity_graph, message_store as msg_store, episode_store
from datetime import datetime as dt

# Importance thresholds
PRUNE_BELOW = 2      # archive below this
MERGE_ABOVE = 7      # distill above this into a summary fact
ARCHIVE_OLD = 30     # days without access before archival consideration


def distill_facts():
    """Find high-importance facts that have been accessed many times.
    Replace with a single summary fact, archive originals.
    """
    with fact_store.get_db() as db:
        rows = db.execute("""
            SELECT id, entity, category, content, importance, access_ct
            FROM facts
            WHERE importance >= ? AND access_ct >= 3
            ORDER BY entity, category
        """, (MERGE_ABOVE,)).fetchall()

    if not rows:
        print("[compaction] nothing to distill")
        return

    # Group by entity+category
    groups = {}
    for row in rows:
        key = (row[1], row[2])  # (entity, category)
        groups.setdefault(key, []).append(row)

    distilled = 0
    for (entity, category), facts in groups.items():
        if len(facts) < 2:
            continue
        # Merge into one summary
        summary_content = f"Summary of {len(facts)} related facts about {entity} ({category}): " + \
            " | ".join(f["content"] for f in facts[:5])
        # Archive originals
        for f in facts:
            fact_store.archive(f[0], emit=False)
        # Write distilled summary
        new_id = fact_store.add(
            entity, category, summary_content,
            importance=max(f["importance"] for f in facts),
            confidence=0.95,
            source="compaction_distill",
        )
        distilled += 1

    print(f"[compaction] distilled {distilled} groups")


def prune_low_importance():
    """Archive facts with importance below threshold."""
    with fact_store.get_db() as db:
        rows = db.execute(
            "SELECT id FROM facts WHERE importance < ?",
            (PRUNE_BELOW,)
        ).fetchall()

    if not rows:
        print("[compaction] nothing to prune")
        return

    for (fid,) in rows:
        fact_store.archive(fid, emit=False)
    print(f"[compaction] pruned {len(rows)} low-importance facts")


def age_out_episodes(days_old=ARCHIVE_OLD):
    """Mark old ended episodes as lower importance (soft archive)."""
    cutoff = dt.now().strftime("%Y-%m-%dT%H:%M:%S")
    # just report; episodes don't have a hard delete path yet
    with episode_store.get_db() as db:
        rows = db.execute("""
            SELECT id, summary FROM episodes
            WHERE ended_at < datetime('now', '-' || ? || ' days')
        """, (days_old,)).fetchall()
    print(f"[compaction] {len(rows)} episodes older than {days_old} days")
    return [dict(r) for r in rows]


def run():
    """Full compaction pass."""
    print(f"[compaction] starting at {dt.now().strftime('%Y-%m-%dT%H:%M:%S')}")
    distill_facts()
    prune_low_importance()
    aged = age_out_episodes()
    print(f"[compaction] done. {len(aged)} old episodes noted.")


if __name__ == "__main__":
    run()
