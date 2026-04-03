"""context_injector.py — Prepends relevant memories to every prompt.
Keeps context fresh, forgets what's stale, never overflows the window.
"""
import fact_store, entity_graph, episode_store, message_store as msg_store

MAX_CONTEXT_TOKENS = 60_000  # conservative; adjust per model
AVG_CHARS_PER_TOKEN = 4


def build_context(
    query=None,
    entity=None,
    session_id=None,
    max_tokens=MAX_CONTEXT_TOKENS,
):
    """Build a memory-prefixed context string for injection into a prompt.

    Args:
        query: keyword to search facts by
        entity: restrict to this entity
        session_id: include recent episode events from this session
        max_tokens: hard limit on total context

    Returns:
        str: formatted memory context, ready to prepend
    """
    lines = []
    used_tokens = 0

    def append(section_name, content, importance=5):
        nonlocal used_tokens
        if not content:
            return
        # rough token estimate
        content_tokens = len(content) // AVG_CHARS_PER_TOKEN
        if used_tokens + content_tokens > max_tokens:
            return  # would overflow; skip
        lines.append(f"[{section_name}]\n{content}")
        used_tokens += content_tokens

    # 1. Entity graph — "doug knows / believes / prefers"
    if entity:
        edges = entity_graph.infer(entity, "likes") or []
        if edges:
            append("entity_graph", f"{entity} likes: {', '.join(edges)}")
        edges = entity_graph.infer(entity, "dislikes") or []
        if edges:
            append("entity_graph", f"{entity} dislikes: {', '.join(edges)}")

    # 2. Structured facts — most important first
    facts = fact_store.search(query=query, entity=entity, limit=10)
    if facts:
        lines.append("[facts]")
        for f in facts[:5]:
            lines.append(f"  [{f['importance']}] {f['content']}")
            used_tokens += len(f["content"]) // AVG_CHARS_PER_TOKEN

    # 3. Recent episodes
    if session_id:
        episodes = episode_store.recent_episodes(limit=3)
        for ep in episodes:
            if ep.get("summary"):
                append("episode", f"[{ep['started_at']}] {ep['summary']}", ep["importance"])

    # 4. Recent messages as context
    if query:
        msgs = msg_store.search(keyword=query, limit=5)
        if msgs:
            buf = []
            for m in msgs:
                buf.append(f"  {m['role']}: {m['content'][:200]}")
            append("messages", "\n".join(buf))

    if not lines:
        return ""

    header = (
        f"--- memory_context ({used_tokens} tokens est.) ---\n"
        "You have the following memory context. Use it to inform your response.\n"
    )
    footer = "\n--- end memory_context ---"
    return header + "\n\n".join(lines) + footer


def inject(query=None, entity=None, session_id=None, max_tokens=MAX_CONTEXT_TOKENS):
    """Returns (context_string, overflowed). If overflowed=True, context was truncated."""
    original_len = max_tokens
    ctx = build_context(query, entity, session_id, max_tokens)
    overflowed = len(ctx) > (original_len * AVG_CHARS_PER_TOKEN)
    return ctx, overflowed


if __name__ == "__main__":
    entity_graph.init()
    fact_store.init()
    episode_store.init()
    msg_store.init()

    # seed some data
    eid = entity_graph.connect("doug", "likes", "coffee", weight=0.9)
    entity_graph.connect("doug", "dislikes", "meetings", weight=0.6)
    fid = fact_store.add("doug", "project", "building memory core for AI", importance=8)

    ctx, overflow = inject(entity="doug", query="memory")
    print(ctx)
    print(f"\noverflowed: {overflow}")
