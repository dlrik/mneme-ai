"""episode_store.py — Session episodes. Groups of related events with shared summary."""
import sqlite3, os
from datetime import datetime as dt

DB = os.path.join(os.path.dirname(__file__), "memory", "episodes.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)

INIT_EPISODES = """CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    summary TEXT DEFAULT '',
    model TEXT DEFAULT '',
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    importance INTEGER DEFAULT 5)"""

INIT_EVENTS = """CREATE TABLE IF NOT EXISTS episode_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL)"""


def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with get_db() as db:
        db.executescript(INIT_EPISODES)
        db.executescript(INIT_EVENTS)


def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def ts():
    return dt.now().strftime("%Y-%m-%dT%H:%M:%S")


def rowdicts(rows):
    """Convert sqlite3.Row objects to dicts."""
    return [dict(row) for row in rows]


def start_episode(session_id, model="", importance=5):
    """Start a new episode. Returns episode id."""
    now = ts()
    with get_db() as db:
        db.execute(
            "INSERT INTO episodes (session_id,started_at,importance,model) VALUES (?,?,?,?)",
            (session_id, now, importance, model),
        )
        eid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"[episode] started eid={eid} session={session_id}")
    return eid


def log_event(episode_id, event_type, content):
    """Add an event to an episode."""
    now = ts()
    with get_db() as db:
        db.execute(
            "INSERT INTO episode_events (episode_id,event_type,content,created_at) VALUES (?,?,?,?)",
            (episode_id, event_type, content, now),
        )
        ev_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return ev_id


def end_episode(episode_id, summary=""):
    """Close an episode with a summary."""
    now = ts()
    with get_db() as db:
        db.execute(
            "UPDATE episodes SET ended_at=?, summary=? WHERE id=?",
            (now, summary, episode_id),
        )


def get_episode(episode_id):
    """Get episode + its events."""
    with get_db() as db:
        ep = db.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone()
        events = db.execute(
            "SELECT * FROM episode_events WHERE episode_id=? ORDER BY created_at",
            (episode_id,),
        ).fetchall()
    return {"episode": dict(ep) if ep else None, "events": rowdicts(events)}


def recent_episodes(limit=10):
    """List most recent episodes."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM episodes ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return rowdicts(rows)


if __name__ == "__main__":
    init()
    eid = start_episode("session-001", model="claude-sonnet-4", importance=7)
    log_event(eid, "user_message", "Tell me about AI memory architectures")
    log_event(eid, "assistant_response", "Here's a layered approach...")
    end_episode(eid, summary="Discussion of AI memory architecture patterns")
    ep = get_episode(eid)
    print(f"episode: {ep['episode']['summary']}, {len(ep['events'])} events")
