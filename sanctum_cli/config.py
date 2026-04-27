"""Configuration management — ~/.sanctum/ directory, profiles, token files."""

import json
import os
from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".sanctum"
DEFAULT_TOKENS_DIR = DEFAULT_CONFIG_DIR / "tokens"

PROFILES = {
    "default": {
        "api_base": "https://core.digitalsanctum.com.au/api",
    },
    "local": {
        "api_base": "http://localhost:8000",
    },
}


def ensure_config_dir() -> Path:
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_CONFIG_DIR


def get_token_file(profile: str = "default") -> Path:
    ensure_config_dir()
    return DEFAULT_TOKENS_DIR / f"{profile}.txt"


def save_token(profile: str, token: str) -> None:
    token_file = get_token_file(profile)
    token_file.write_text(token)
    token_file.chmod(0o600)


def load_token(profile: str = "default") -> str | None:
    token_file = get_token_file(profile)
    if token_file.exists():
        return token_file.read_text().strip()
    return None


def get_api_base(profile: str = "default") -> str:
    return PROFILES.get(profile, PROFILES["default"])["api_base"]


def get_config_path() -> Path:
    ensure_config_dir()
    return DEFAULT_CONFIG_DIR / "config.json"


def load_config() -> dict:
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    config_path = get_config_path()
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def get_env_dir() -> Path | None:
    config = load_config()
    env_dir = config.get("env_dir")
    if env_dir:
        p = Path(env_dir)
        if p.exists():
            return p
    return None
