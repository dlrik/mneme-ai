#!/usr/bin/env python3
"""sync-all-to-obsidian.py — Sync all agents' memories to the Obsidian vault.

Run:
    python scripts/sync-all-to-obsidian.py

Updates:
    mneme          → AI-Knowledge/agents/mneme/
    openclaw       → AI-Knowledge/agents/openclaw/
    deer-flow      → AI-Knowledge/agents/deer-flow/
    claude-code    → AI-Knowledge/agents/claude-code/
"""

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
VAULT = Path.home() / "AI-Knowledge"

SCRIPTS = {
    "mneme": None,  # special: handled inline via direct import
    "openclaw": "export_openclaw_to_obsidian.py",
    "deer-flow": "export_deerflow_to_obsidian.py",
    "claude-code": "export_claude_code_to_obsidian.py",
}


def run(name: str, script_path: Path | None):
    print(f"\n{'='*50}")
    print(f"Syncing: {name}")
    print(f"{'='*50}")

    if script_path is None:
        # mneme — run directly from the package
        sys.path.insert(0, str(SCRIPT_DIR.parent))  # mneme-ai/
        try:
            from mneme.obsidian_exporter import export_full_dump
            from mneme.fact_store import init as fs_init
            from mneme.entity_graph import init as eg_init
            from mneme.episode_store import init as eps_init
            fs_init(); eg_init(); eps_init()
            result = export_full_dump("doug")
            print(f"  Exported: {list(result.keys())}")
        except Exception as e:
            print(f"  Error: {e}")
        return

    full_path = SCRIPT_DIR / script_path
    if not full_path.exists():
        print(f"  ✗ Script not found: {full_path}")
        return

    try:
        result = subprocess.run(
            [sys.executable, str(full_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"  ✗ Exit code {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")
    except Exception as e:
        print(f"  ✗ Error: {e}")


def main():
    print(f"Obsidian Vault: {VAULT}")
    print(f"Scripts dir: {SCRIPT_DIR}")
    print(f"Starting sync...\n")

    for name, script in SCRIPTS.items():
        run(name, script)

    print(f"\n{'='*50}")
    print("All agents synced to Obsidian vault.")
    print(f"Open Obsidian → {VAULT}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
