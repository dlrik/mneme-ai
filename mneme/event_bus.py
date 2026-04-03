"""event_bus.py — Pub/sub coordination layer. All memory modules emit here."""
from datetime import datetime

_listeners = {}  # key: "table.event", value: [callbacks]


def on(table, event, callback):
    """Subscribe to events. callback(data) is called on emit."""
    key = f"{table}.{event}"
    _listeners.setdefault(key, []).append(callback)
    print(f"[bus] subscribe {key}")


def emit(table, event, data=None):
    """Broadcast event to all matching subscribers."""
    key = f"{table}.{event}"
    for cb in _listeners.get(key, []):
        try:
            cb(data or {})
        except Exception as e:
            print(f"[bus] callback error on {key}: {e}")


def show_listeners():
    """Debug: list all active subscriptions."""
    return dict(_listeners)


if __name__ == "__main__":
    # smoke test
    events = []

    def tracker(d):
        events.append(d)

    on("fact", "written", tracker)
    emit("fact", "written", {"id": 42})
    print(f"tracked: {events}")
