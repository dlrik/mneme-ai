"""message_store.py — Immutable append-only raw message log with DAG summaries."""
import sqlite3, os, hashlib, datetime as dt

DB = os.path.join(os.path.dirname(__file__), "memory", "msgs.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)

INIT = """CREATE TABLE IF NOT EXISTS msgs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tokens INTEGER DEFAULT 0,
    source TEXT DEFAULT '',
    checksum TEXT NOT NULL,
    created_at TEXT NOT NULL)"""

DAG_INIT = """CREATE TABLE IF NOT EXISTS dag (
    node_id TEXT PRIMARY KEY,
    parent_id TEXT,
    depth INTEGER DEFAULT 0,
    summary TEXT,
    model TEXT DEFAULT '',
    created_at TEXT NOT NULL)"""


def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with get_db() as db:
        db.executescript(INIT)
        db.executescript(DAG_INIT)


def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def ts():
    return dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def append(role, content, tokens=0, source=""):
    """Append a raw message. Returns message id."""
    ck = hashlib.md5(content.encode()).hexdigest()[:12]
    now = ts()
    with get_db() as db:
        db.execute(
            "INSERT INTO msgs (role,content,tokens,source,checksum,created_at) VALUES (?,?,?,?,?,?)",
            (role, content, tokens, source, ck, now),
        )
        mid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"[msg] id={mid} role={role}")
    return mid


def search(keyword=None, role=None, limit=20):
    """Full-text search on message content."""
    sql = "SELECT * FROM msgs"
    params = []
    if keyword:
        sql += " WHERE content LIKE ?"
        params.append(f"%{keyword}%")
    if role:
        sql += " AND role=?" if keyword else " WHERE role=?"
        params.append(role)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_db() as db:
        return db.execute(sql, params).fetchall()


if __name__ == "__main__":
    init()
    mid = append("system", "memory_core online", source="smoke_test")
    print(f"message {mid} logged")
