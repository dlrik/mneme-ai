"""fact_store.py — Structured SQLite facts + importance decay."""
import sqlite3, os, datetime as dt

DB = os.path.join(os.path.dirname(__file__), "memory", "facts.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)

INIT = """CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    content TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 5,
    confidence REAL NOT NULL DEFAULT 0.9,
    source TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    access_ct INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT NOT NULL)"""

INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_entity ON facts(entity)"


def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with get_db() as db:
        db.executescript(INIT)
        db.execute(INDEX_SQL)
        db.commit()


def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def ts():
    return dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def add(entity, category, content, importance=5, confidence=0.9, source=""):
    """Add a fact. Returns fact id."""
    now = ts()
    with get_db() as db:
        db.execute(
            "INSERT INTO facts (entity,category,content,importance,confidence,source,created_at,updated_at,access_ct,last_seen) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (entity, category, content, importance, confidence, source, now, now, 0, now),
        )
        fid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"[fact] id={fid} entity={entity} category={category}")
    return fid


def search(query=None, entity=None, category=None, limit=20):
    """Search facts by keyword and/or entity/category."""
    sql = "SELECT * FROM facts WHERE 1=1"
    params = []
    if query:
        sql += " AND content LIKE ?"
        params.append(f"%{query}%")
    if entity:
        sql += " AND entity=?"
        params.append(entity)
    if category:
        sql += " AND category=?"
        params.append(category)
    sql += " ORDER BY importance DESC LIMIT ?"
    params.append(limit)
    with get_db() as db:
        return db.execute(sql, params).fetchall()


def decay():
    """Importance-weighted decay. Important facts fade slow; trivia fades fast."""
    with get_db() as db:
        rows = db.execute("SELECT id, importance FROM facts").fetchall()
        n = 0
        for fid, imp in rows:
            rate = 0.01 if imp >= 7 else (0.05 if imp >= 5 else 0.1)
            db.execute(
                "UPDATE facts SET importance=MAX(1,importance-?) WHERE id=?",
                (rate, fid),
            )
            n += 1
        db.commit()
        print(f"[fact] decayed {n} facts")


def archive(fid, emit=True):
    """Permanently delete a fact."""
    with get_db() as db:
        db.execute("DELETE FROM facts WHERE id=?", (fid,))
        db.commit()
    if emit:
        print(f"[fact] archived fid={fid}")


if __name__ == "__main__":
    init()
    fid = add("test", "check", "Claude forgot context", importance=5)
    print(f"fact {fid} written")
    results = search("context")
    print(f"search returned {len(results)} row(s)")
