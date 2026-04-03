"""MCP server for mneme. Uses stdio transport for local agent integration.

Run: python -m mneme_mcp.server
"""

import json
import sys
from mneme_mcp.tools import (
    TOOLS,
    call_mneme_remember,
    call_mneme_retrieve,
    call_mneme_search,
    call_mneme_know,
    call_mneme_episode_start,
    call_mneme_episode_log,
    call_mneme_episode_end,
    call_mneme_context,
    call_mneme_health,
)

TOOL_HANDLERS = {
    "mneme_remember": lambda args: call_mneme_remember(
        entity=args["entity"],
        category=args["category"],
        content=args["content"],
        importance=args.get("importance", 5),
        confidence=args.get("confidence", 0.9),
    ),
    "mneme_retrieve": lambda args: call_mneme_retrieve(
        query=args.get("query"),
        entity=args.get("entity"),
        category=args.get("category"),
        limit=args.get("limit", 20),
    ),
    "mneme_search": lambda args: call_mneme_search(
        query=args["query"],
        top_k=args.get("top_k", 5),
        entity=args.get("entity"),
    ),
    "mneme_know": lambda args: call_mneme_know(who=args["who"]),
    "mneme_episode_start": lambda args: call_mneme_episode_start(
        session_id=args["session_id"],
        model=args.get("model", ""),
        importance=args.get("importance", 5),
    ),
    "mneme_episode_log": lambda args: call_mneme_episode_log(
        episode_id=args["episode_id"],
        event_type=args["event_type"],
        content=args["content"],
    ),
    "mneme_episode_end": lambda args: call_mneme_episode_end(
        episode_id=args["episode_id"],
        summary=args.get("summary", ""),
    ),
    "mneme_context": lambda args: call_mneme_context(
        query=args.get("query"),
        entity=args.get("entity"),
        max_tokens=args.get("max_tokens", 2000),
    ),
    "mneme_health": lambda args: call_mneme_health(),
}


def handle_request(data: dict) -> dict:
    """Handle an MCP JSON-RPC request."""
    method = data.get("method", "")
    request_id = data.get("id")

    # Respond to requests
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mneme", "version": "0.1.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        params = data.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in TOOL_HANDLERS:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }

        try:
            result = TOOL_HANDLERS[tool_name](arguments)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2),
                        }
                    ]
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": f"Tool error: {e}"},
            }

    # Notifications (no response needed)
    if method.endswith("/notification"):
        return None

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main():
    """Read JSON-RPC requests from stdin, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            response = handle_request(data)
            if response is not None:
                print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            print(json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error"},
            }), flush=True)


if __name__ == "__main__":
    main()
