"""server.py — FastAPI server for mneme. HTTP API for all memory layers.

Run: uvicorn mneme.server:app --host 0.0.0.0 --port 8765
"""

import sys, os
from datetime import datetime as dt

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Import all memory layers
from mneme import fact_store, message_store, entity_graph, episode_store, vec_mem
from mneme import context_injector, compaction

app = FastAPI(title="Mneme API", version="1.0.0")

# CORS — allow everything for now
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class RememberRequest(BaseModel):
    entity: str
    category: str
    content: str
    importance: int = 5
    confidence: float = 0.9
    source: str = ""
    role: str = "assistant"


class GraphConnectRequest(BaseModel):
    subject: str
    predicate: str
    object: str
    weight: float = 1.0
    source: str = ""


class EpisodeStartRequest(BaseModel):
    session_id: str
    model: str = ""
    importance: int = 5


class EpisodeLogRequest(BaseModel):
    episode_id: int
    event_type: str
    content: str


class EpisodeEndRequest(BaseModel):
    episode_id: int
    summary: str = ""


class VecAddRequest(BaseModel):
    content: str
    entity: Optional[str] = None
    source: str = ""


class ContextInjectRequest(BaseModel):
    query: Optional[str] = None
    entity: Optional[str] = None
    session_id: Optional[str] = None
    max_tokens: int = 60000


class MessageLogRequest(BaseModel):
    role: str
    content: str
    tokens: int = 0
    source: str = ""


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    try:
        conn = fact_store.get_db()
        fact_count = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        conn.close()
    except Exception:
        fact_count = 0
    try:
        ep_conn = episode_store.get_db()
        ep_count = ep_conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        ep_conn.close()
    except Exception:
        ep_count = 0
    return {
        "status": "ok",
        "version": "0.1.0",
        "facts": fact_count,
        "chunks": vec_mem.count(),
        "episodes": ep_count,
    }


@app.get("/")
def ui():
    """Mneme web dashboard."""
    return FileResponse("ui/index.html")


@app.get("/ui/{filename}")
def ui_static(filename):
    return FileResponse(f"ui/{filename}")


# ---------------------------------------------------------------------------
# Fact store
# ---------------------------------------------------------------------------


@app.post("/facts")
def facts_add(req: RememberRequest):
    fid = fact_store.add(
        req.entity, req.category, req.content,
        req.importance, req.confidence, req.source,
    )
    return {"fact_id": fid}


@app.get("/facts")
def facts_search(
    query: str = Query(None),
    entity: str = Query(None),
    category: str = Query(None),
    limit: int = Query(20),
):
    rows = fact_store.search(query=query, entity=entity, category=category, limit=limit)
    return {"results": [dict(r) for r in rows], "count": len(rows)}


@app.post("/facts/decay")
def facts_decay():
    fact_store.decay()
    return {"status": "done"}


# ---------------------------------------------------------------------------
# Message store
# ---------------------------------------------------------------------------


@app.post("/messages")
def messages_append(req: MessageLogRequest):
    mid = message_store.append(req.role, req.content, req.tokens, req.source)
    return {"message_id": mid}


@app.get("/messages")
def messages_search(
    keyword: str = Query(None),
    role: str = Query(None),
    limit: int = Query(20),
):
    rows = message_store.search(keyword=keyword, role=role, limit=limit)
    return {"results": [dict(r) for r in rows], "count": len(rows)}


# ---------------------------------------------------------------------------
# Entity graph
# ---------------------------------------------------------------------------


@app.post("/graph")
def graph_connect(req: GraphConnectRequest):
    eid = entity_graph.connect(
        req.subject, req.predicate, req.object, req.weight, req.source,
    )
    return {"edge_id": eid}


@app.get("/graph/infer")
def graph_infer(
    subject: str = Query(...),
    predicate: str = Query(...),
):
    results = entity_graph.infer(subject, predicate)
    return {"subject": subject, "predicate": predicate, "objects": results}


@app.get("/graph/neighbors")
def graph_neighbors(entity: str = Query(...)):
    rows = entity_graph.query(subject=entity) + entity_graph.query(object=entity)
    return {"entity": entity, "edges": [dict(r) for r in rows], "count": len(rows)}


@app.get("/graph/know")
def graph_know(who: str = Query(...)):
    rows = entity_graph.know(who)
    return {"who": who, "edges": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Episode store
# ---------------------------------------------------------------------------


@app.post("/episodes")
def episodes_start(req: EpisodeStartRequest):
    eid = episode_store.start_episode(req.session_id, req.model, req.importance)
    return {"episode_id": eid}


@app.post("/episodes/log")
def episodes_log(req: EpisodeLogRequest):
    ev_id = episode_store.log_event(req.episode_id, req.event_type, req.content)
    return {"event_id": ev_id}


@app.post("/episodes/end")
def episodes_end(req: EpisodeEndRequest):
    episode_store.end_episode(req.episode_id, req.summary)
    return {"episode_id": req.episode_id, "status": "ended"}


@app.get("/episodes/recent")
def episodes_recent(limit: int = Query(10)):
    eps = episode_store.recent_episodes(limit=limit)
    return {"episodes": eps, "count": len(eps)}


@app.get("/episodes/{episode_id}")
def episodes_get(episode_id: int):
    ep = episode_store.get_episode(episode_id)
    if not ep["episode"]:
        raise HTTPException(404, "episode not found")
    return ep


@app.get("/episodes/for_entity")
def episodes_for_entity(entity: str = Query(...)):
    eps = episode_store.recent_episodes(limit=20)
    matching = [e for e in eps if entity.lower() in (e.get("summary") or "").lower()]
    return {"entity": entity, "episodes": matching, "count": len(matching)}


# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------


@app.post("/vec")
def vec_add(req: VecAddRequest):
    meta = {"entity": req.entity, "source": req.source} if req.entity or req.source else None
    chunk_id = vec_mem.add(req.content, meta)
    return {"chunk_id": chunk_id}


@app.get("/vec/search")
def vec_search(
    query: str = Query(...),
    top_k: int = Query(5),
    entity: str = Query(None),
):
    hits = vec_mem.search(query, top_k=top_k, entity=entity)
    return {"query": query, "hits": hits, "count": len(hits)}


@app.post("/vec/reembed")
def vec_reembed():
    count = vec_mem.reembed_pending()
    return {"reembedded": count}


@app.get("/vec/count")
def vec_count():
    return {"count": vec_mem.count()}


@app.get("/vec/related")
def vec_related(content: str = Query(...), top_k: int = Query(5)):
    hits = vec_mem.search(content, top_k=top_k)
    return {"content": content, "hits": hits, "count": len(hits)}


@app.post("/messages/reembed")
def messages_reembed():
    result = vec_mem.reembed_all()
    return {"status": "ok", **result}


@app.get("/vec/sync/status")
def vec_sync_status():
    status = vec_mem.get_sync_status()
    return {"status": "ok", **status}


# ---------------------------------------------------------------------------
# Context injector
# ---------------------------------------------------------------------------


@app.post("/context/inject")
def context_inject(req: ContextInjectRequest):
    ctx, overflowed = context_injector.inject(
        query=req.query,
        entity=req.entity,
        session_id=req.session_id,
        max_tokens=req.max_tokens,
    )
    return {"context": ctx, "overflowed": overflowed}


# ---------------------------------------------------------------------------
# Compaction
# ---------------------------------------------------------------------------


@app.post("/compaction/run")
def compaction_run():
    compaction.run()
    return {"status": "done"}


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def on_startup():
    fact_store.init()
    message_store.init()
    entity_graph.init()
    episode_store.init()
    vec_mem.init()
    print("[mneme] all stores initialized")


def main():
    """Run the mneme server. Called by `mneme-server` entry point."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
