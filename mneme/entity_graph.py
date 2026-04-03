"""entity_graph.py — Knows who knows what about whom. Edge-weighted relationship store."""
import sqlite3, os
from datetime import datetime as dt

DB = os.path.join(os.path.dirname(__file__), "memory", "graph.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)

INIT = """CREATE TABLE IF NOT EXISTS edges (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    subject    TEXT NOT NULL,
    predicate  TEXT NOT NULL,
    object     TEXT NOT NULL,
    weight     REAL NOT NULL DEFAULT 1.0,
    source     TEXT DEFAULT '',
    created_at TEXT NOT NULL)"""

INDEX = "CREATE INDEX IF NOT EXISTS idx_subject ON edges(subject)"


def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with get_db() as db:
        db.executescript(INIT)
        db.execute(INDEX)
        db.commit()


def get_db():
    return sqlite3.connect(DB)


def ts():
    return dt.now().strftime("%Y-%m-%dT%H:%M:%S")


def connect(subject, predicate, object, weight=1.0, source=""):
    """Add a directed edge: subject --predicate--> object."""
    now = ts()
    with get_db() as db:
        db.execute(
            "INSERT INTO edges (subject,predicate,object,weight,source,created_at) VALUES (?,?,?,?,?,?)",
            (subject, predicate, object, weight, source, now),
        )
        eid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"[graph] eid={eid} {subject} --{predicate}--> {object}")
    return eid


def query(subject=None, predicate=None, object=None):
    """Find edges matching pattern. Pass any combination of subject/predicate/object."""
    sql = "SELECT * FROM edges WHERE 1=1"
    params = []
    if subject:   sql += " AND subject=?";   params.append(subject)
    if predicate: sql += " AND predicate=?"; params.append(predicate)
    if object:   sql += " AND object=?";    params.append(object)
    with get_db() as db:
        return db.execute(sql, params).fetchall()


def know(who):
    """Return all facts known about a given entity."""
    return query(object=who)


def strength(subject, predicate, object):
    """Return edge weight between subject and object via predicate, or 0 if none."""
    rows = query(subject=subject, predicate=predicate, object=object)
    return rows[0][4] if rows else 0.0


def infer(subject, predicate):
    """Forward-chain: find all objects reachable from subject via predicate."""
    rows = query(subject=subject, predicate=predicate)
    return [row[3] for row in rows]  # row[3] = object


if __name__ == "__main__":
    init()
    connect("doug", "likes", "coffee", weight=0.9, source="conversation")
    connect("doug", "dislikes", "smalltalk", weight=0.7, source="conversation")
    connect("doug", "works_at", "tech_company", weight=1.0, source="inferred")
    results = infer("doug", "likes")
    print(f"doug likes: {results}")
