"""Authentication — interactive login, token resolution, 2FA."""

import getpass
import logging
import os

from sanctum_cli.config import get_api_base, get_env_dir, load_token, save_token
from sanctum_client.client import get as api_get
from sanctum_client.client import post as api_post
from sanctum_client.client import set_api_base, set_api_token
from sanctum_client.identity import load_agent_tokens, resolve_agent_token

log = logging.getLogger(__name__)


def resolve_env(env: str | None = None) -> tuple[str, str]:
    """Resolve environment to API base URL and profile name.

    Returns:
        (api_base, profile_name)
    """
    if env == "local":
        return "http://localhost:8000", "default"
    return get_api_base("default"), "default"


def ensure_auth(env: str | None = None, agent: str | None = None) -> None:
    """Ensure we have a valid API token. Falls back through:
    1. SANCTUM_API_TOKEN env var
    2. --agent flag -> SANCTUM_TOKEN_<AGENT>
    3. Saved token file
    4. Interactive login
    """
    api_base, profile = resolve_env(env)
    set_api_base(api_base)

    load_agent_tokens(str(get_env_dir()) if get_env_dir() else None)

    token = os.getenv("SANCTUM_API_TOKEN", "")

    if not token and agent:
        token = resolve_agent_token(agent)

    if not token:
        saved = load_token(profile)
        if saved:
            set_api_token(saved)
            try:
                api_get("/projects", params={"limit": "1"})
                return
            except Exception:
                pass

    if not token:
        token = interactive_login(api_base, profile)

    set_api_token(token)


def interactive_login(api_base: str, profile: str) -> str:
    """Interactive email/password login with 2FA support."""
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")

    result = api_post("/token", json={"email": email, "password": password})

    if isinstance(result, dict) and result.get("detail") == "2FA_REQUIRED":
        totp_secret = os.getenv("SANCTUM_TOTP_SECRET", "")
        if totp_secret:
            import pyotp
            totp = pyotp.TOTP(totp_secret)
            code = totp.now()
        else:
            code = getpass.getpass("2FA Code: ")
        result = api_post("/token", json={"email": email, "password": password, "totp_code": code})

    if isinstance(result, dict) and "access_token" in result:
        token = result["access_token"]
        save_token(profile, token)
        return token

    raise RuntimeError(f"Authentication failed: {result}")
