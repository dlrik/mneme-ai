#!/usr/bin/env python3
"""export_deerflow_to_obsidian.py — Export DeerFlow threads + agents to Obsidian vault.

Run:
    python scripts/export_deerflow_to_obsidian.py

Reads from: DeerFlow API at http://localhost:8001
Exports to: ~/AI-Knowledge/agents/deer-flow/
"""

import json
import re
import httpx
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_URL = "http://localhost:8001"
DST = Path.home() / "AI-Knowledge" / "agents" / "deer-flow"


def _ymd():
    return datetime.now().strftime("%Y-%m-%d")


def _parse_timestamp(ts: str) -> str:
    """Parse a unix timestamp string or ISO date to YYYY-MM-DD."""
    if not ts:
        return _ymd()
    try:
        # It's a unix timestamp string like "1775249869"
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        pass
    # Try as ISO string
    try:
        return ts[:10]
    except Exception:
        return _ymd()


def _frontmatter(title: str, tags: list[str], date: str = "") -> str:
    tags_str = " ".join(f"#{t}" for t in tags)
    meta = ["---", f"title: {title}", f"created: {date or _ymd()}", f"tags: [{tags_str}]", "---"]
    return "\n".join(meta) + "\n\n"


def _slug(s: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", s)
    slug = re.sub(r"\s+", "-", slug).strip("-")
    return slug[:60] or "untitled"


def _clean_content(text: str) -> str:
    """Remove internal LangGraph thinking/reasoning tags from content."""
    # Remove <additional_kwargs> blocks
    try:
        text = re.sub(r"<additional_kwargs>.*?</additional_kwargs>", "", text, flags=re.DOTALL)
    except re.error:
        pass
    # Remove response_metadata blocks
    try:
        text = re.sub(r"<response_metadata>.*?</response_metadata>", "", text, flags=re.DOTALL)
    except re.error:
        pass
    # Remove <think>...</think> thinking blocks
    try:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    except re.error:
        pass
    # Collapse whitespace
    try:
        text = re.sub(r"\n{3,}", "\n\n", text)
    except re.error:
        pass
    return text.strip()


def _extract_messages(state: dict) -> list[dict]:
    """Extract readable messages from a DeerFlow thread state."""
    messages = []

    # State structure: { thread_id, status, values: { messages, thread_data, title }, ... }
    values = state.get("values", {})
    if isinstance(values, dict):
        msgs = values.get("messages", []) or []
    else:
        msgs = []

    for msg in msgs:
        if not isinstance(msg, dict):
            continue

        msg_type = msg.get("type", "?")
        raw_content = msg.get("content", "")

        if not raw_content:
            continue

        # Determine label
        if msg_type == "human":
            label = "User"
        elif msg_type == "ai":
            label = msg.get("name") or "Assistant"
        elif msg_type == "tool":
            label = f"[tool: {msg.get('name', '?')}]"
        else:
            label = msg_type.capitalize() if msg_type else "Message"

        # Extract content - can be str, list of blocks, or tool result dict
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            # List of content blocks [{type: "text", text: ...}, ...]
            parts = []
            for block in raw_content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        parts.append(f"[tool result]\n{block.get('content', '')}")
                elif isinstance(block, str):
                    parts.append(block)
            content = "\n".join(parts)
        elif isinstance(raw_content, dict):
            # Tool result: {"query": ..., "results": [...], ...}
            content = json.dumps(raw_content, indent=2)[:1000]
        else:
            continue

        content = _clean_content(content)

        # Skip empty or system messages
        if not content.strip() or msg_type == "system":
            continue

        messages.append({"role": label, "content": content})

    return messages


def export_deerflow():
    DST.mkdir(parents=True, exist_ok=True)

    print(f"Exporting DeerFlow data to {DST}\n")

    # ── 1. Export agent SOUL.md files ────────────────────────────────────────
    print("Fetching agents...")
    try:
        resp = httpx.get(f"{BASE_URL}/api/agents", timeout=10)
        agents_data = resp.json().get("agents", [])
    except Exception as e:
        print(f"  Warning: could not fetch agents: {e}")
        agents_data = []

    for agent in agents_data:
        name = agent.get("name", "unknown")
        soul = agent.get("soul", "")
        if soul:
            lines = [_frontmatter(f"SOUL: {name}", ["deerflow", "agent", name])]
            lines.append(f"# {name} — SOUL\n")
            lines.append(soul.strip())
            out_path = DST / f"agent_{name}_soul.md"
            out_path.write_text("\n".join(lines))
            print(f"  ✓ agent SOUL: {name}")

    # ── 2. Export threads ────────────────────────────────────────────────────
    print("\nFetching threads...")
    try:
        resp = httpx.post(f"{BASE_URL}/api/threads/search",
                          json={"query": ""}, timeout=10)
        threads = resp.json()
    except Exception as e:
        print(f"  Warning: could not fetch threads: {e}")
        threads = []

    print(f"  Found {len(threads)} threads")

    for thread in threads:
        tid = thread.get("thread_id", "unknown")
        metadata = thread.get("metadata", {})
        agent_name = metadata.get("agent_name", "unknown")
        status = thread.get("status", "?")
        created = _parse_timestamp(thread.get("created_at", ""))
        title = f"Thread {tid[:8]}"

        try:
            state_resp = httpx.get(f"{BASE_URL}/api/threads/{tid}", timeout=10)
            state_data = state_resp.json()

            # Get title from state values
            values = state_data.get("values", {})
            title_from_state = values.get("title", "") if isinstance(values, dict) else ""
            if title_from_state:
                # Remove <畔在想...> tags from title
                title_from_state = re.sub(r"<.*?>", "", title_from_state).strip()

            # Try to extract messages from state
            messages = _extract_messages(state_data)

            if messages:
                # Find first user message as title
                for m in messages:
                    if m["role"].lower() in ("user", "human"):
                        first_user = m["content"][:80].replace("\n", " ")
                        title_from_state = first_user
                        break

                # Write conversation
                lines = [_frontmatter(title, ["deerflow", "thread", agent_name], created)]
                lines.append(f"# {title}\n")
                lines.append(f"_Agent: {agent_name} | Status: {status} | Created: {created}_\n")

                if title_from_state:
                    lines.append(f"\n> {title_from_state}\n")

                lines.append("\n---\n\n")
                for i, m in enumerate(messages):
                    lines.append(f"## {m['role']}\n")
                    lines.append(f"{m['content']}\n\n")

                out_path = DST / f"thread_{tid[:8]}.md"
                out_path.write_text("\n".join(lines))
                print(f"  ✓ thread {tid[:8]} ({agent_name}): {title_from_state or 'no title'[:50]}")
            else:
                # Empty thread - just record metadata
                lines = [_frontmatter(title, ["deerflow", "thread", agent_name], created)]
                lines.append(f"# {title}\n")
                lines.append(f"_Agent: {agent_name} | Status: {status} | Created: {created}_\n")
                lines.append("\n_No conversation history found._\n")
                out_path = DST / f"thread_{tid[:8]}.md"
                out_path.write_text("\n".join(lines))
                print(f"  - thread {tid[:8]} ({agent_name}): empty")

        except Exception as e:
            print(f"  ✗ thread {tid[:8]}: error - {e}")

    # ── 3. Write index ───────────────────────────────────────────────────────
    index_lines = [
        _frontmatter("DeerFlow Memory", ["deerflow", "index"]),
        "# DeerFlow\n",
        f"_Exported: {_ymd()}_\n",
        f"Agents: {len(agents_data)} | Threads: {len(threads)}\n",
        "## Agents\n",
    ]
    for agent in agents_data:
        name = agent.get("name", "?")
        index_lines.append(f"- [[agent_{name}_soul.md|{name}]]")
    index_lines.append("\n## Threads\n")
    for thread in threads:
        tid = thread.get("thread_id", "")
        metadata = thread.get("metadata", {})
        agent = metadata.get("agent_name", "?")
        index_lines.append(f"- [[thread_{tid[:8]}.md|{tid[:8]}]] ({agent})")
    (DST / "index.md").write_text("\n".join(index_lines))

    print(f"\nDone. Exported to {DST}")


if __name__ == "__main__":
    export_deerflow()
