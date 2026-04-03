#!/usr/bin/env python3
"""export_claude_code_to_obsidian.py — Export Claude Code session memory to Obsidian vault.

Run:
    python scripts/export_claude_code_to_obsidian.py

Exports:
    ~/.claude/plans/                                  → plans/
    ~/.claude/projects/-home-doug/memory/             → memory/
    ~/.claude/projects/-home-doug/*.jsonl             → sessions/
    ~/.claude/projects/-home-doug/MEMORY.md           → index.md
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

SRC_PLANS = Path.home() / ".claude" / "plans"
SRC_MEMORY = Path.home() / ".claude" / "projects" / "-home-doug" / "memory"
SRC_INDEX = Path.home() / ".claude" / "projects" / "-home-doug" / "MEMORY.md"
SRC_SESSIONS = Path.home() / ".claude" / "projects" / "-home-doug"
DST = Path.home() / "AI-Knowledge" / "agents" / "claude-code"


def _ymd():
    return datetime.now().strftime("%Y-%m-%d")


def _frontmatter(title: str, tags: list[str], date: str = "") -> str:
    tags_str = " ".join(f"#{t}" for t in tags)
    meta = ["---", f"title: {title}", f"created: {date or _ymd()}", f"tags: [{tags_str}]", "---"]
    return "\n".join(meta) + "\n\n"


def _slug(s: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", s)
    slug = re.sub(r"\s+", "-", slug).strip("-")
    return slug[:60] or "untitled"


def _parse_timestamp(ts: str) -> str:
    if not ts:
        return _ymd()
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return ts[:16] if len(ts) >= 16 else ts


def _extract_text_content(content) -> str:
    """Extract readable text from a message content block (str or list)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", "").strip())
                elif block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    inp = block.get("input", {})
                    # Summarize tool calls briefly
                    if isinstance(inp, dict):
                        desc = inp.get("desc") or inp.get("description") or str(inp)[:100]
                        parts.append(f"[tool: {name}]")
                elif block.get("type") == "thinking":
                    pass  # skip thinking blocks
        return " ".join(parts).strip()
    return ""


def _export_session(jsonl_path: Path) -> Path | None:
    """Parse a Claude Code session JSONL and export as markdown."""
    try:
        entries = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        if not entries:
            return None

        # Get session ID from first entry
        first = entries[0]
        session_id = None
        session_date = _ymd()
        for e in entries:
            if e.get("sessionId"):
                session_id = e["sessionId"]
                break

        slug_id = jsonl_path.stem[:8]
        title = f"Session {slug_id}"

        # Collect user/assistant messages in order
        messages = []
        for entry in entries:
            msg_type = entry.get("type")
            if msg_type not in ("user", "assistant"):
                continue

            msg = entry.get("message", {})
            role = msg.get("role", msg_type.capitalize() if msg_type else "?")
            raw_content = msg.get("content", "")
            text = _extract_text_content(raw_content)

            if not text:
                continue

            # Get timestamp from entry
            ts = _parse_timestamp(entry.get("timestamp", ""))

            messages.append({"role": role.capitalize(), "content": text, "ts": ts})

        if not messages:
            return None

        # Build markdown
        lines = [_frontmatter(title, ["claude-code", "session"], messages[0]["ts"] if messages else "")]
        lines.append(f"# {title}\n")
        lines.append(f"_Session: `{session_id or jsonl_path.stem}`_\n")
        lines.append(f"_File: `{jsonl_path.name}`_\n")
        lines.append(f"_Messages: {len(messages)}_\n\n---\n\n")

        for m in messages:
            ts = m["ts"]
            role = m["role"]
            content = m["content"]
            lines.append(f"## {role}  `{ts}`\n")
            lines.append(f"{content}\n\n")

        out_path = DST / "sessions" / f"{slug_id}.md"
        out_path.write_text("\n".join(lines))
        return out_path
    except Exception as e:
        print(f"    Warning: could not parse {jsonl_path.name}: {e}")
        return None


def export_claude_code():
    DST.mkdir(parents=True, exist_ok=True)
    (DST / "plans").mkdir(exist_ok=True)
    (DST / "memory").mkdir(exist_ok=True)
    (DST / "sessions").mkdir(exist_ok=True)

    print(f"Exporting Claude Code memory to {DST}\n")

    # ── Plans ────────────────────────────────────────────────────────────────
    if SRC_PLANS.exists():
        for plan_file in sorted(SRC_PLANS.iterdir()):
            if plan_file.suffix != ".md":
                continue
            title = plan_file.stem.replace("-", " ").title()
            content = plan_file.read_text()
            m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if m:
                title = m.group(1).strip()

            slug = _slug(plan_file.stem)
            lines = [_frontmatter(title, ["claude-code", "plan"])]
            lines.append(f"# {title}\n")
            lines.append(f"_Plan file: `{plan_file.name}`_\n")
            lines.append(content)
            out_path = DST / "plans" / f"{slug}.md"
            out_path.write_text("\n".join(lines))
            print(f"  ✓ plan: {plan_file.name}")
    else:
        print("  (no plans directory)")

    # ── Memory files ─────────────────────────────────────────────────────────
    if SRC_MEMORY.exists():
        for mem_file in sorted(SRC_MEMORY.iterdir()):
            if mem_file.suffix != ".md":
                continue
            dest = DST / "memory" / mem_file.name
            shutil.copy2(mem_file, dest)
            print(f"  ✓ memory: {mem_file.name}")
    else:
        print("  (no memory directory)")

    # ── Session transcripts ───────────────────────────────────────────────────
    print("\n  Exporting sessions...")
    session_count = 0
    if SRC_SESSIONS.exists():
        for jsonl_file in sorted(SRC_SESSIONS.glob("*.jsonl")):
            result = _export_session(jsonl_file)
            if result:
                print(f"  ✓ session: {result.name}")
                session_count += 1
    if session_count == 0:
        print("  (no sessions found)")

    # ── MEMORY.md index ───────────────────────────────────────────────────────
    if SRC_INDEX.exists():
        content = SRC_INDEX.read_text()
        lines = [_frontmatter("Claude Code Memory Index", ["claude-code", "index"])]
        lines.append("# Claude Code Memory\n\n")
        lines.append("_Exported from `~/.claude/projects/-home-doug/MEMORY.md`_\n\n")
        lines.append(content)
        (DST / "index.md").write_text("\n".join(lines))
        print(f"\n  ✓ index: MEMORY.md")
    else:
        print("  (no MEMORY.md index found)")

    print(f"\nDone. Exported to {DST}")


if __name__ == "__main__":
    export_claude_code()
