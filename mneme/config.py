"""Configuration for mneme. Reads from ~/.config/mneme/config.json or environment variables."""

import os
import json
from pathlib import Path

CONFIG_PATH = Path(os.path.expanduser("~/.config/mneme/config.json"))

# Data directory (relative to this file, stored in mneme/memory/)
DATA_DIR = Path(__file__).parent / "memory"


def get_config():
    """Load config from ~/.config/mneme/config.json. Returns {} if not found."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_api_key():
    """Get VOYAGE_API_KEY from config file or environment variable.

    Priority: config.json > VOYAGE_API_KEY env var
    """
    cfg = get_config()
    key = cfg.get("env", {}).get("VOYAGE_API_KEY", "")
    if key:
        return key
    return os.getenv("VOYAGE_API_KEY", "")


def get_data_dir():
    """Return the data directory, creating it if needed."""
    d = DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d
