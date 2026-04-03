"""obsidian_exporter.py — Export mneme memory to an Obsidian vault."""

import os
from datetime import datetime
from pathlib import Path

VAULT_PATH = Path.home() / "AI-Knowledge" / "agents" / "mneme"

# ─── helpers ────────────────────────────────────────────────────────────────

def _vault() -> Path:
    p = VAULT_PATH
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ymd() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _frontmatter(title: str, tags: list[str], entity: str = "") -> str:
    tags_str = " ".join(f"#{t}" for t in tags)
    meta = [
        "---",
        f"title: {title}",
        f"created: {_ymd()}",
        f"tags: [{tags_str}]",
    ]
    if entity:
        meta.append(f"entity: {entity}")
    meta.append("---")
    return "\n".join(meta) + "\n\n"


# ─── export functions ────────────────────────────────────────────────────────

def export_facts(facts, filename: str = "facts.md") -> Path:
    """Write a fact list as a markdown note. facts can be sqlite3.Row or dict."""
    vault = _vault()
    path = vault / filename
    lines = [_frontmatter("Facts", ["mneme", "facts"])]

    for f in facts:
        fd = dict(f) if not isinstance(f, dict) else f
        imp = fd.get("importance", 5)
        badge = "🔴" if imp >= 8 else "🟡" if imp >= 5 else "⚪️"
        entity = fd.get("entity", "?")
        category = fd.get("category", "general")
        content = fd.get("content", "")
        date = fd.get("created_at", "")[:10]
        lines.append(f"{badge} [{entity}/{category}] *{date}*")
        lines.append(f"  {content}\n")

    path.write_text("\n".join(lines))
    return path


def export_entity(entity: str, facts, graph_edges) -> Path:
    """Write everything mneme knows about a single entity as a note.

    facts: result of fact_store.search() — sqlite3.Row objects
    graph_edges: result of entity_graph.query() — sqlite3.Row objects
    """
    vault = _vault()
    path = vault / f"entity_{entity}.md"

    lines = [_frontmatter(f"Mneme: {entity}", ["mneme", "entity", entity], entity=entity)]
    lines.append(f"# {entity}\n")

    # Facts
    if facts:
        lines.append("## Facts\n")
        for f in facts:
            f_dict = dict(f)
            imp = f_dict.get("importance", 5)
            lines.append(f"- [{imp}/10] {f_dict.get('content', '')}  ")
            lines.append(f"  _category: {f_dict.get('category', 'general')}_\n")

    # Graph
    if graph_edges:
        lines.append("\n## Relationships\n")
        for e in graph_edges:
            e_dict = dict(e)
            pred = e_dict.get("predicate", "→")
            obj = e_dict.get("object", "?")
            weight = e_dict.get("weight", 1)
            lines.append(f"- **{entity}** {pred} → {obj} (conf: {weight:.0%})\n")

    path.write_text("\n".join(lines))
    return path


def export_episode(episode: dict, events: list[dict]) -> Path:
    """Write a single episode as a note."""
    vault = _vault()
    session_id = episode.get("session_id", "unknown").replace("/", "_")
    path = vault / f"episode_{session_id}.md"

    started = episode.get("started_at", "")[:10]
    summary = episode.get("summary", "")
    importance = episode.get("importance", 5)

    lines = [_frontmatter(f"Episode: {session_id}", ["mneme", "episode"], entity=episode.get("entity", ""))]
    lines.append(f"# Episode: {session_id}\n")
    lines.append(f"- **Started:** {started}")
    lines.append(f"- **Importance:** {importance}/10")
    if summary:
        lines.append(f"- **Summary:** {summary}\n")

    if events:
        lines.append("\n## Events\n")
        for ev in events:
            ev_type = ev.get("event_type", "?")
            content = ev.get("content", "")
            ts = ev.get("created_at", "")[:19]
            lines.append(f"- [{ts}] *{ev_type}:* {content}\n")

    path.write_text("\n".join(lines))
    return path


def export_vector_search(query: str, hits: list[dict]) -> Path:
    """Write a vector search session as a note."""
    vault = _vault()
    safe_q = query.replace("/", "_").replace(" ", "_")[:40]
    path = vault / f"search_{safe_q}.md"

    lines = [_frontmatter(f"Search: {query}", ["mneme", "search"])]
    lines.append(f"# Vector Search: `{query}`\n")
    lines.append(f"_Retrieved {len(hits)} results_\n")

    for i, h in enumerate(hits, 1):
        dist = h.get("distance", 0)
        content = h.get("content", "")
        meta = h.get("metadata", {})
        entity = meta.get("entity", "")
        category = meta.get("category", "")
        sim = max(0, int((1 - dist) * 100))
        lines.append(f"## {i}. [{sim}% similar]\n")
        if entity or category:
            lines.append(f"_entity: {entity} | category: {category}_\n")
        lines.append(f"{content}\n")

    path.write_text("\n".join(lines))
    return path


def export_full_dump(entity: str = "doug") -> dict[str, Path]:
    """Export everything about an entity to the vault. Returns dict of written files."""
    from mneme import fact_store as fs
    from mneme import entity_graph as eg
    from mneme import episode_store as eps

    # Fetch all facts (sqlite3.Row objects)
    facts = fs.search(entity=entity, limit=100) or []

    # Fetch graph edges (sqlite3.Row objects)
    edges = eg.query(subject=entity) or []

    # Fetch recent episodes
    recent_eps = eps.recent_episodes(limit=10) or []

    written = {}

    # Export entity note
    written["entity"] = export_entity(entity, facts, edges)

    # Export facts
    written["facts"] = export_facts(facts)

    # Export episodes
    for ep in recent_eps:
        ep_id = ep.get("id")
        if ep_id:
            try:
                ep_data = eps.get_episode(ep_id)
                written[f"episode_{ep.get('session_id', str(ep_id)).replace('/', '_')}"] = export_episode(
                    ep, ep_data.get("events", [])
                )
            except Exception:
                pass

    return written


# ─── CLI ─────────────────────────────────────────────────────────────────────

def cli():
    """Run the exporter from the command line.

    Usage:
        mneme-export              # export doug's memory
        mneme-export <entity>     # export specific entity
        mneme-export --vault <path>  # set vault path
    """
    import argparse

    parser = argparse.ArgumentParser(description="Export mneme memory to an Obsidian vault")
    parser.add_argument("entity", nargs="?", default="doug", help="Entity to export (default: doug)")
    parser.add_argument("--vault", type=Path, default=VAULT_PATH,
                        help=f"Vault path (default: {VAULT_PATH})")
    args = parser.parse_args()

    global VAULT_PATH
    VAULT_PATH = args.vault

    from mneme.fact_store import init as fs_init
    from mneme.entity_graph import init as eg_init
    from mneme.episode_store import init as eps_init

    fs_init()
    eg_init()
    eps_init()

    print(f"Exporting mneme memory for '{args.entity}' to {VAULT_PATH}...")
    result = export_full_dump(args.entity)

    if not result:
        print("No files written — is the mneme database empty?")
        return

    print(f"\nExported {len(result)} file(s):")
    for name, path in result.items():
        print(f"  ✓ {path.relative_to(VAULT_PATH.parent.parent)}")


if __name__ == "__main__":
    cli()
