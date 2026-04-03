"""memory_api.py — Unified remember/retrieve interface.
Coordinates: fact_store + message_store + event_bus.
"""
import fact_store, message_store, event_bus as _bus


def remember(entity, category, content, importance=5, confidence=0.9, source="", role="assistant"):
    """Write to facts + messages, emit event. Returns (fact_id, msg_id)."""
    msg_id = message_store.append(role, content, source=source)
    fact_id = fact_store.add(entity, category, content, importance, confidence, source)
    _bus.emit("memory", "remembered", {"entity": entity, "fact_id": fact_id})
    return fact_id, msg_id


def retrieve(query=None, entity=None, category=None, limit=20):
    """Search structured facts. Pass query= for keyword, entity= for entity filter."""
    return fact_store.search(query=query, entity=entity, category=category, limit=limit)


def decay():
    """Run importance decay on all facts."""
    fact_store.decay()


def init():
    """Boot all stores."""
    fact_store.init()
    message_store.init()


if __name__ == "__main__":
    init()
    fid, mid = remember("doug", "preference", "likes coffee", importance=7)
    results = retrieve("coffee")
    print(f"stored: fid={fid}, mid={mid}, retrieved {len(results)} fact(s)")
