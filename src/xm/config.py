"""Configuration management"""

import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".xm"
CONFIG_FILE = CONFIG_DIR / "config.toml"
DB_FILE = CONFIG_DIR / "sessions.db"


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def get_api_key(provider: str = "openai") -> str:
    """Get API key from env var."""
    env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }
    key = os.environ.get(env_map.get(provider, ""), "")
    if not key:
        # Try generic XM_API_KEY
        key = os.environ.get("XM_API_KEY", "")
    return key


def get_base_url(provider: str = "openai") -> str | None:
    """Get custom base URL if set."""
    env_map = {
        "openai": "OPENAI_BASE_URL",
        "anthropic": "ANTHROPIC_BASE_URL",
        "deepseek": "DEEPSEEK_BASE_URL",
    }
    return os.environ.get(env_map.get(provider, ""))
