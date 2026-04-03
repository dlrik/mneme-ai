"""vec_mem.py — Chroma-backed vector store with Voyage AI embeddings.

ANN search via Chroma's in-memory store (persistent to disk).
Collection: "memory_chunks" — documents, embeddings, metadata.
"""
import os, json, hashlib
from datetime import datetime as dt
from pathlib import Path

# Chroma + Voyage
import chromadb
from chromadb.config import Settings as ChromaSettings

from mneme.config import get_data_dir, get_api_key

DB_DIR = get_data_dir()
COLLECTION_NAME = "memory_chunks"
EMBED_MODEL = "voyage-4-large"
EMBED_URL = "https://api.voyageai.com/v1/embeddings"
EMBED_DIM = 1024

# Persistent Chroma store
PERSIST_PATH = DB_DIR / "chroma_data"
PERSIST_PATH.mkdir(parents=True, exist_ok=True)

# Sync state (persisted to disk)
_SYNC_STATE_PATH = DB_DIR / "sync_state.json"


def _load_sync_state():
    """Load sync state from disk."""
    try:
        with open(_SYNC_STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {"last_sync": None, "last_error": None, "consecutive_errors": 0}


def _save_sync_state(state):
    """Persist sync state to disk."""
    try:
        with open(_SYNC_STATE_PATH, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def get_sync_status():
    """Return sync status for the API."""
    state = _load_sync_state()
    return {
        "last_sync": state.get("last_sync"),
        "last_error": state.get("last_error"),
        "consecutive_errors": state.get("consecutive_errors", 0),
    }


def _sync_error(msg):
    """Record a sync error state and return error result."""
    state = _load_sync_state()
    state["last_error"] = msg
    state["consecutive_errors"] = state.get("consecutive_errors", 0) + 1
    _save_sync_state(state)
    print(f"[vec] sync error: {msg}")
    return {"added": 0, "skipped": 0, "error": msg}


def _embed_voyage(text, api_key):
    """Call Voyage AI /embeddings endpoint. Returns embedding vector or None."""
    if not api_key:
        return None
    import urllib.request
    try:
        payload = json.dumps({"input": text[:8000], "model": "voyage-4-large"}).encode()
        req = urllib.request.Request(
            EMBED_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
            return data["data"][0]["embedding"]
    except Exception as e:
        print(f"[vec] Voyage embed error: {e}")
        return None


def _init_chroma():
    """Create/open the Chroma persistent collection."""
    client = chromadb.PersistentClient(path=str(PERSIST_PATH))
    try:
        collection = client.create_collection(COLLECTION_NAME)
    except Exception:
        collection = client.get_collection(COLLECTION_NAME)
    return client, collection


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init():
    """Boot Chroma. Idempotent."""
    client, collection = _init_chroma()
    print(f"[vec] Chroma ready — collection '{COLLECTION_NAME}', persist={PERSIST_PATH}")
    return collection


def add(content, metadata=None, api_key=""):
    """Embed content via Voyage AI and store in Chroma. Returns chunk id."""
    key = api_key or get_api_key()
    meta = metadata or {}
    now = ts()
    meta["created_at"] = now

    chunk_id = hashlib.md5(content.encode()).hexdigest()[:16]

    embedding = _embed_voyage(content, key)
    if embedding:
        _client, collection = _init_chroma()
        collection.add(
            documents=[content],
            embeddings=[embedding],
            metadatas=[meta],
            ids=[chunk_id],
        )
        print(f"[vec] added chunk {chunk_id}, embedding=yes, chars={len(content)}")
    else:
        _client, collection = _init_chroma()
        collection.add(
            documents=[content],
            metadatas=[{**meta, "embedding_pending": True}],
            ids=[chunk_id],
        )
        print(f"[vec] added chunk {chunk_id}, embedding=no (pending), chars={len(content)}")
    return chunk_id


def search(query, top_k=5, entity=None, api_key=""):
    """ANN search via Chroma. Returns list of {content, metadata, distance} dicts."""
    key = api_key or get_api_key()
    if not key:
        print("[vec] search skipped — no VOYAGE_API_KEY")
        return []

    query_emb = _embed_voyage(query, key)
    if not query_emb:
        return []

    _client, collection = _init_chroma()

    where_clause = {"entity": entity} if entity else None
    results = collection.query(
        query_texts=[query],
        query_embeddings=[query_emb],
        n_results=top_k,
        where=where_clause,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    if results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            hits.append({
                "chunk_id": chunk_id,
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
    print(f"[vec] search '{query}' → {len(hits)} hits")
    return hits


def reembed_pending(api_key=""):
    """Find chunks stored without embeddings and embed them now."""
    key = api_key or get_api_key()
    if not key:
        print("[vec] reembed skipped — no API key")
        return 0

    _client, collection = _init_chroma()
    try:
        results = collection.get(where={"embedding_pending": True})
    except Exception:
        return 0

    if not results["ids"]:
        print("[vec] no pending embeddings")
        return 0

    count = 0
    for i, doc_id in enumerate(results["ids"]):
        content = results["documents"][i]
        meta = results["metadatas"][i]
        emb = _embed_voyage(content, key)
        if emb:
            collection.update(
                ids=[doc_id],
                embeddings=[emb],
                metadatas=[{**meta, "embedding_pending": False}],
            )
            count += 1
    print(f"[vec] reembedded {count} pending chunks")
    return count


def reembed_all(api_key=""):
    """Backfill all messages from message_store into ChromaDB via Voyage AI.

    Returns dict with counts: added, skipped, errors.
    """
    import sqlite3

    key = api_key or get_api_key()
    if not key:
        print("[vec] reembed skipped — no VOYAGE_API_KEY")
        return {"added": 0, "skipped": 0, "errors": "no API key"}

    MSG_DB = get_data_dir() / "msgs.db"
    if not MSG_DB.exists():
        return {"added": 0, "skipped": 0, "errors": f"messages DB not found: {MSG_DB}"}

    try:
        conn = sqlite3.connect(str(MSG_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, role, content, source, created_at FROM msgs ORDER BY id"
        ).fetchall()
        conn.close()
    except Exception as e:
        return {"added": 0, "skipped": 0, "errors": str(e)}

    if not rows:
        return {"added": 0, "skipped": 0, "errors": None}

    _client, collection = _init_chroma()
    existing_ids = set(collection.get()['ids'])

    added = 0
    skipped = 0
    error_msgs = []

    for row in rows:
        msg_id = row["id"]
        chunk_id = f"msg_{msg_id}"

        if chunk_id in existing_ids:
            skipped += 1
            continue

        content = row["content"]
        role = row["role"]
        source = row["source"] or ""
        created_at = row["created_at"] or ""

        if not content or not content.strip():
            skipped += 1
            continue

        embedding = _embed_voyage(content, key)
        if not embedding:
            error_msgs.append(f"msg_id={msg_id}: embed failed")
            skipped += 1
            continue

        meta = {
            "path": "",
            "source": source or "message_store",
            "role": role,
            "msg_id": msg_id,
            "model": EMBED_MODEL,
            "updated_at": created_at,
        }

        try:
            collection.add(
                documents=[content],
                embeddings=[embedding],
                metadatas=[meta],
                ids=[chunk_id],
            )
            added += 1
        except Exception as e:
            error_msgs.append(f"msg_id={msg_id}: {e}")
            skipped += 1

    print(f"[vec] reembed messages: added={added}, skipped={skipped}, errors={len(error_msgs)}")
    return {
        "added": added,
        "skipped": skipped,
        "errors": error_msgs[:10] if error_msgs else None,
    }


def count():
    """Total chunks in collection."""
    _client, collection = _init_chroma()
    return collection.count()


def ts():
    return dt.now().strftime("%Y-%m-%dT%H:%M:%S")


if __name__ == "__main__":
    collection = init()
    cid = add(
        "Claude forgot previous conversation context — agent has no memory of prior decisions",
        metadata={"entity": "claude", "source": "learnings"},
    )
    hits = search("Claude memory context", top_k=3)
    print(f"search hits: {len(hits)}")
    for h in hits:
        print(f"  [{h['chunk_id']}] dist={h['distance']:.4f} | {h['content'][:60]}...")
    print(f"total chunks: {count()}")
