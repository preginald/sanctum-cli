"""Authentication — interactive login, token resolution, 2FA, identity guard."""

import logging
import os

from sanctum_cli.config import (
    get_api_base,
    get_env_dir,
    load_user_token,
    save_user_token,
)
from sanctum_cli.identity_map import check_agent_for
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


def ensure_auth(
    env: str | None = None,
    agent: str | None = None,
    user: str | None = None,
) -> None:
    """Ensure we have a valid API token.

    Exactly one of --agent or --user must be provided — the CLI enforces
    this at the root level. The operator agent is blocked from implicit use.

    Resolution:
    1. --agent → resolve_agent_token(agent) → SANCTUM_TOKEN_<AGENT>
    2. --user → load_user_token(email) or interactive_login()
    3. Fallback: SANCTUM_API_TOKEN env var (deprecated, warns)
    """
    api_base, profile = resolve_env(env)
    set_api_base(api_base)
    load_agent_tokens(str(get_env_dir()) if get_env_dir() else None)

    token: str | None = None
    resolved_agent: str | None = agent

    if agent:
        token = resolve_agent_token(agent)
        if not token:
            raise RuntimeError(
                f"No token configured for --agent {agent}. "
                f"Set SANCTUM_TOKEN_{agent.upper().replace('-', '_')} "
                f"or create an .env.{agent} file."
            )

    elif user:
        token = load_user_token(user)
        if not token:
            token = _interactive_login(api_base, user)
            save_user_token(user, token)
        resolved_agent = user

    else:
        token = os.getenv("SANCTUM_API_TOKEN", "")
        if token:
            log.warning(
                "DEPRECATED: SANCTUM_API_TOKEN used without --agent or --user. "
                "Use --agent <name> or --user <email> for proper attribution."
            )
        resolved_agent = "operator"

    if not token:
        raise RuntimeError("No authentication token available. Use --agent or --user.")

    set_api_token(token)
    return resolved_agent


def check_command_identity(
    domain: str,
    command: str,
    current_agent: str | None,
) -> None:
    """Validate the current agent is appropriate for the domain command.

    Raises SystemExit(1) on hard blocks (operator on non-operator commands).
    Prints warnings for mismatches.
    """
    message = check_agent_for(domain, command, current_agent)
    if message:
        import sys

        from sanctum_cli.display import print_error
        print_error(message)
        sys.exit(1)


def _interactive_login(api_base: str, email: str) -> str:
    """Interactive email/password login with 2FA support."""
    from getpass import getpass

    password = getpass(f"Password for {email}: ")

    try:
        from sanctum_client.client import get_client
        client = get_client()
        _ = client.base_url
    except Exception:
        pass

    from sanctum_client.client import API_BASE
    old = API_BASE
    try:
        from sanctum_client.client import set_api_base as set_base
        set_base(api_base)
        result = api_post("/token", json={"email": email, "password": password})
    finally:
        if old:
            from sanctum_client.client import set_api_base as set_base
            set_base(old)

    if isinstance(result, dict) and result.get("detail") == "2FA_REQUIRED":
        totp_secret = os.getenv("SANCTUM_TOTP_SECRET", "")
        if totp_secret:
            import pyotp
            totp = pyotp.TOTP(totp_secret)
            code = totp.now()
        else:
            code = getpass("2FA Code: ")
        result = api_post("/token", json={"email": email, "password": password, "totp_code": code})

    if isinstance(result, dict) and "access_token" in result:
        return result["access_token"]

    raise RuntimeError(f"Authentication failed: {result}")

