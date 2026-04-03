# Mneme — Semantic Memory for AI Agents

**Mneme** gives your AI agents persistent, queryable memory — with semantic vector search, a knowledge graph, and episodic tracking.

> Named after the Greek goddess of memory, mother of the Muses.

## Why Mneme?

AI agents forget everything between sessions. Mneme fixes that.

- **Semantic search** — find "coffee preference" when you ask about "drinks Doug likes" (no keyword matching required)
- **Knowledge graph** — entity triples with forward-chaining inference
- **Episodes** — session-level context so agents know what happened before
- **Prompt-ready context** — built-in context injector for any LLM prompt
- **Web UI** — inspect your memory at `http://localhost:8765`

ByteRover uses keyword search (BM25). Mneme uses semantic vectors. They're not the same thing.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Your AI Agent                      │
│        (Claude Code, DeerFlow, Cursor, etc.)         │
└──────────────┬──────────────────────────────────────┘
               │ MCP tools / HTTP API
               ▼
┌──────────────────────────────────────────────────────┐
│                   Mneme Server                       │
│                  (FastAPI :8765)                     │
├──────────┬──────────┬──────────┬──────────────────┤
│  Facts   │  Graph   │ Episodes │  Vector (Chroma) │
│ SQLite   │ SQLite   │  SQLite  │   + Voyage AI    │
└──────────┴──────────┴──────────┴──────────────────┘
```

## Quick Start

```bash
pip install mneme-ai

# Set your API key
export VOYAGE_API_KEY="pa-..."

# Start the server
mneme-server
# or: python -m mneme.server

# Visit http://localhost:8765 for the dashboard
```

## MCP Server (recommended)

Connect Mneme to any MCP-compatible agent (Claude Code, Cursor, Cline, Windsurf):

```bash
# Install with MCP support
pip install "mneme-ai[mcp]"

# Start the MCP server
mneme-mcp
```

Then configure your agent to use the MCP server at `localhost:8765`.

## API

### Store a fact

```bash
curl -X POST http://localhost:8765/facts \
  -H "Content-Type: application/json" \
  -d '{"entity": "doug", "category": "preference", "content": "likes dark roast coffee", "importance": 7}'
```

### Semantic search

```bash
curl "http://localhost:8765/vec/search?query=coffee+preferences&top_k=5"
```

### Get full context for a prompt

```bash
curl -X POST http://localhost:8765/context/inject \
  -H "Content-Type: application/json" \
  -d '{"entity": "doug", "max_tokens": 2000}'
```

### Knowledge graph

```bash
# What does the agent know about "doug"?
curl "http://localhost:8765/graph/know?who=doug"
```

## Python API

```python
from mneme import fact_store, vec_mem, entity_graph

# Store facts
fact_store.add("doug", "preference", "likes coffee", importance=7)

# Semantic search
results = vec_mem.search("coffee preferences", top_k=5)

# Knowledge graph
entity_graph.connect("doug", "likes", "coffee")
```

## Memory Layers

| Layer | What it does |
|---|---|
| **Structured facts** | SQLite, importance 1-10, decay over time |
| **Raw messages** | Immutable append-only log, checksums |
| **Entity graph** | Subject→predicate→object triples with inference |
| **Episodes** | Session grouping + event logging |
| **Vector store** | ChromaDB + Voyage AI (1024-dim embeddings) |
| **Context injector** | Token-budget-aware memory for prompts |
| **Compaction** | Distill → merge → prune → age-out |

## Configuration

Config file: `~/.config/mneme/config.json`

```json
{
  "env": {
    "VOYAGE_API_KEY": "pa-..."
  }
}
```

Or via environment variable: `VOYAGE_API_KEY=pa-...`

## vs ByteRover

| | ByteRover | Mneme |
|---|---|---|
| Search | BM25 keyword | **Semantic vectors** |
| Embeddings | None | **Voyage AI (1024-dim)** |
| Knowledge graph | No | **Yes** |
| Episodes | No | **Yes** |
| Agent integration | MCP | MCP + HTTP API |
| Auto-indexing | Manual | **Auto on every write** |
| Install | `curl install.sh` | `pip install` |

## License

MIT
