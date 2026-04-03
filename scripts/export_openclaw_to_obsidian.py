#!/usr/bin/env python3
"""export_openclaw_to_obsidian.py — Export OpenClaw memory journal to Obsidian vault.

Run:
    python scripts/export_openclaw_to_obsidian.py

Exports ~/.openclaw/memory/main.sqlite chunks → ~/AI-Knowledge/agents/openclaw/
"""

import sqlite3, re
from pathlib import Path

SRC_DB = Path.home() / ".openclaw" / "memory" / "main.sqlite"
DST = Path.home() / "AI-Knowledge" / "agents" / "openclaw"


def _ymd():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def _frontmatter(title: str, tags: list[str], date: str = "") -> str:
    tags_str = " ".join(f"#{t}" for t in tags)
    meta = ["---", f"title: {title}", f"created: {date or _ymd()}", f"tags: [{tags_str}]", "---"]
    return "\n".join(meta) + "\n\n"


def _slug(title: str) -> str:
    """Make a safe filename from a title."""
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", title)
    slug = re.sub(r"\s+", "-", slug).strip("-")
    return slug[:60] or "untitled"


def export_openclaw():
    DST.mkdir(parents=True, exist_ok=True)

    if not SRC_DB.exists():
        print(f"ERROR: {SRC_DB} not found")
        return

    con = sqlite3.connect(str(SRC_DB))
    cur = con.cursor()

    # Get all files
    files = cur.execute("SELECT path, source FROM files WHERE source='memory'").fetchall()
    print(f"Found {len(files)} memory files in OpenClaw\n")

    written = []

    for path, source in files:
        # Get all chunks for this file, sorted by start_line
        chunks = cur.execute(
            "SELECT start_line, text FROM chunks WHERE path=? ORDER BY start_line",
            (path,),
        ).fetchall()

        if not chunks:
            continue

        # Reconstruct: sort by line, deduplicate by content
        seen_texts = set()
        lines_out = []
        for start_line, text in chunks:
            # Normalize: strip leading/trailing whitespace
            norm = text.strip()
            if norm and norm not in seen_texts:
                seen_texts.add(norm)
                lines_out.append(norm)

        # Skip if it's the MEMORY.md index (too meta for the vault)
        clean_path = path.replace("memory/", "")
        if clean_path == "MEMORY.md":
            filename = "openclaw-memory-index.md"
        else:
            filename = _slug(clean_path.replace("/", "-").replace(".md", "")) + ".md"

        # Extract a readable title from the first line of content
        title = path
        if lines_out:
            first = lines_out[0].strip()
            if first.startswith("#"):
                title = first.lstrip("#").strip()

        # Build frontmatter
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", path)
        date = date_match.group(1) if date_match else ""

        content_lines = [_frontmatter(title, ["openclaw", "journal", source], date)]
        content_lines.append(f"# {title}\n")
        content_lines.append(f"_Source: `{path}`_\n")
        for chunk_text in lines_out:
            content_lines.append(chunk_text)

        out_path = DST / filename
        out_path.write_text("\n\n".join(content_lines))
        written.append((path, out_path.name))
        print(f"  ✓ {path} → {out_path.name}")

    # Also write an index note
    index_content = [
        _frontmatter("OpenClaw Memory Index", ["openclaw", "index"]),
        "# OpenClaw Memory\n",
        f"_Exported: {_ymd()}_\n",
        "## Files\n",
    ]
    for orig_path, filename in sorted(written):
        index_content.append(f"- [[{filename}|{orig_path}]]")
    index_content.append("\n## Summary\n")
    index_content.append(f"Total files exported: {len(written)}")
    (DST / "index.md").write_text("\n".join(index_content))

    con.close()
    print(f"\nExported {len(written)} files to {DST}")


if __name__ == "__main__":
    export_openclaw()
