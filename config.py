import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "multi-terminal"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "terminal_count": 4,
    "terminal_emulator": "gnome-terminal",
    "auto_tile": True,
    "use_tmux": True,
    "theme": "system",
}


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    ensure_config_dir()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    ensure_config_dir()
    merged = {**DEFAULT_CONFIG, **config}
    with open(CONFIG_FILE, "w") as f:
        json.dump(merged, f, indent=2)
