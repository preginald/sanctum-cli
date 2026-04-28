"""Agent identity resolution — shared between sanctum-cli and sanctum-mcp.

Maps agent names to Core API tokens via environment variables.
The token map matches SYS-057 AgentIdentityMiddleware.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

log = logging.getLogger(__name__)

TOKEN_ENV_MAP = {
    "sanctum-architect": "SANCTUM_TOKEN_ARCHITECT",
    "sanctum-scribe": "SANCTUM_TOKEN_SCRIBE",
    "sanctum-sentinel": "SANCTUM_TOKEN_SENTINEL",
    "sanctum-surgeon": "SANCTUM_TOKEN_SURGEON",
    "sanctum-oracle": "SANCTUM_TOKEN_ORACLE",
    "sanctum-chat": "SANCTUM_TOKEN_CHAT",
    "sanctum-hermes": "SANCTUM_TOKEN_HERMES",
    "sanctum-mock": "SANCTUM_TOKEN_MOCK",
    "sanctum-guardian": "SANCTUM_TOKEN_GUARDIAN",
}

AGENT_ALIASES = {
    "sanctum-code": "sanctum-architect",
}

SHORT_NAMES = {
    "architect": "sanctum-architect",
    "scribe": "sanctum-scribe",
    "sentinel": "sanctum-sentinel",
    "surgeon": "sanctum-surgeon",
    "oracle": "sanctum-oracle",
    "chat": "sanctum-chat",
    "hermes": "sanctum-hermes",
    "mock": "sanctum-mock",
    "guardian": "sanctum-guardian",
}

AGENT_TOKEN_MAP: dict[str, str] = {}


def load_agent_tokens(env_dir: str | None = None) -> dict[str, str]:
    """Load per-agent tokens from env vars and optional .env.* files."""
    global AGENT_TOKEN_MAP

    AGENT_TOKEN_MAP.clear()

    for name, env_var in TOKEN_ENV_MAP.items():
        val = os.getenv(env_var, "")
        if val:
            AGENT_TOKEN_MAP[name] = val

    if env_dir:
        env_path = Path(env_dir)
        for name in SHORT_NAMES.values():
            env_file = env_path / f".env.{name.replace('sanctum-', '')}"
            if env_file.exists():
                load_dotenv(env_file, override=True)
                env_var = TOKEN_ENV_MAP.get(name, "")
                if env_var:
                    val = os.getenv(env_var, "")
                    if val:
                        AGENT_TOKEN_MAP[name] = val

    for alias, canonical in AGENT_ALIASES.items():
        if canonical in AGENT_TOKEN_MAP and alias not in AGENT_TOKEN_MAP:
            AGENT_TOKEN_MAP[alias] = AGENT_TOKEN_MAP[canonical]

    if AGENT_TOKEN_MAP:
        log.debug("Loaded agent tokens: %s", ", ".join(sorted(AGENT_TOKEN_MAP)))
    else:
        log.debug("No agent tokens configured; falling back to SANCTUM_API_TOKEN")

    return AGENT_TOKEN_MAP


def resolve_agent_token(agent_name: str | None) -> str:
    """Resolve an agent name to its Core API token.

    Args:
        agent_name: Short name (e.g. 'operator') or full name (e.g. 'sanctum-operator').

    Returns:
        The API token string, or empty string if not found.
    """
    if not agent_name:
        return ""

    agent_name = agent_name.lower().strip()

    full_name = SHORT_NAMES.get(agent_name, agent_name)

    if full_name in AGENT_TOKEN_MAP:
        return AGENT_TOKEN_MAP[full_name]

    if full_name in AGENT_ALIASES:
        canonical = AGENT_ALIASES[full_name]
        return AGENT_TOKEN_MAP.get(canonical, "")

    return ""
