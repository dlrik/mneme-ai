"""MCP tools for mneme memory layer."""

import httpx
from typing import Any

BASE_URL = "http://localhost:8765"


def make_request(method: str, path: str, data: dict | None = None) -> dict[str, Any]:
    """Make HTTP request to mneme server."""
    url = f"{BASE_URL}{path}"
    if method == "GET":
        resp = httpx.get(url, params=data, timeout=10)
    else:
        resp = httpx.request(method, url, json=data, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Tool definitions (for MCP manifest)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "mneme_remember",
        "description": "Store a fact in long-term memory. Use when you learn something about a user or project that should be remembered.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "The entity this fact is about (e.g. 'doug', 'project-x')"},
                "category": {"type": "string", "enum": ["preference", "knowledge", "context", "behavior", "goal", "correction"], "description": "Type of fact"},
                "content": {"type": "string", "description": "The fact content to remember"},
                "importance": {"type": "integer", "default": 5, "description": "Importance 1-10, default 5"},
                "confidence": {"type": "number", "default": 0.9, "description": "Confidence 0-1"},
            },
            "required": ["entity", "category", "content"],
        },
    },
    {
        "name": "mneme_retrieve",
        "description": "Search structured facts in long-term memory by keyword or entity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword search query"},
                "entity": {"type": "string", "description": "Filter by entity"},
                "category": {"type": "string", "description": "Filter by category"},
                "limit": {"type": "integer", "default": 20, "description": "Max results"},
            },
        },
    },
    {
        "name": "mneme_search",
        "description": "Semantic vector search over all memory — finds conceptually related content without exact keyword matches.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language query"},
                "top_k": {"type": "integer", "default": 5, "description": "Number of results"},
                "entity": {"type": "string", "description": "Filter by entity"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "mneme_know",
        "description": "Query the knowledge graph — get all facts known about an entity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "who": {"type": "string", "description": "Entity name"},
            },
            "required": ["who"],
        },
    },
    {
        "name": "mneme_episode_start",
        "description": "Start a new session episode (e.g. at the start of a conversation).",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Unique session identifier"},
                "model": {"type": "string", "description": "LLM model used"},
                "importance": {"type": "integer", "default": 5},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "mneme_episode_log",
        "description": "Log an event to the current session episode.",
        "input_schema": {
            "type": "object",
            "properties": {
                "episode_id": {"type": "integer", "description": "Episode ID from mneme_episode_start"},
                "event_type": {"type": "string", "description": "Type: message, tool_call, result, etc."},
                "content": {"type": "string", "description": "Event content"},
            },
            "required": ["episode_id", "event_type", "content"],
        },
    },
    {
        "name": "mneme_episode_end",
        "description": "End a session episode.",
        "input_schema": {
            "type": "object",
            "properties": {
                "episode_id": {"type": "integer"},
                "summary": {"type": "string", "description": "Optional episode summary"},
            },
            "required": ["episode_id"],
        },
    },
    {
        "name": "mneme_context",
        "description": "Get full memory context string for injection into an LLM prompt. Returns relevant facts, graph knowledge, and recent episodes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query to focus context around"},
                "entity": {"type": "string", "description": "Entity to get context about"},
                "max_tokens": {"type": "integer", "default": 2000},
            },
        },
    },
    {
        "name": "mneme_health",
        "description": "Check if mneme server is running and get memory stats.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


# ---------------------------------------------------------------------------
# Tool implementations (call these when handling MCP requests)
# ---------------------------------------------------------------------------

def call_mneme_remember(entity: str, category: str, content: str, importance: int = 5, confidence: float = 0.9) -> dict:
    return make_request("POST", "/facts", {
        "entity": entity,
        "category": category,
        "content": content,
        "importance": importance,
        "confidence": confidence,
        "source": "mcp",
    })


def call_mneme_retrieve(query: str = None, entity: str = None, category: str = None, limit: int = 20) -> dict:
    params = {"limit": limit}
    if query:
        params["query"] = query
    if entity:
        params["entity"] = entity
    if category:
        params["category"] = category
    return make_request("GET", "/facts", params)


def call_mneme_search(query: str, top_k: int = 5, entity: str = None) -> dict:
    params = {"query": query, "top_k": top_k}
    if entity:
        params["entity"] = entity
    return make_request("GET", "/vec/search", params)


def call_mneme_know(who: str) -> dict:
    return make_request("GET", "/graph/know", {"who": who})


def call_mneme_episode_start(session_id: str, model: str = "", importance: int = 5) -> dict:
    return make_request("POST", "/episodes", {
        "session_id": session_id,
        "model": model,
        "importance": importance,
    })


def call_mneme_episode_log(episode_id: int, event_type: str, content: str) -> dict:
    return make_request("POST", "/episodes/log", {
        "episode_id": episode_id,
        "event_type": event_type,
        "content": content,
    })


def call_mneme_episode_end(episode_id: int, summary: str = "") -> dict:
    return make_request("POST", "/episodes/end", {
        "episode_id": episode_id,
        "summary": summary,
    })


def call_mneme_context(query: str = None, entity: str = None, max_tokens: int = 2000) -> dict:
    return make_request("POST", "/context/inject", {
        "query": query,
        "entity": entity,
        "max_tokens": max_tokens,
    })


def call_mneme_health() -> dict:
    return make_request("GET", "/health", {})
