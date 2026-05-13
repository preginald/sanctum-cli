"""Proactive token lifecycle management for Sanctum auth tokens.

Supports JWT expiry preflight, automatic OIDC refresh, and local caching.
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

TOKEN_URL = "https://auth.digitalsanctum.com.au/oauth/token"
AUDIENCE = "sanctum-ai-router"
SCOPE = "openid profile email router:invoke router:admin"
CACHE_FILE = Path.home() / ".sanctum" / "router-token-cache.json"
CACHE_MODE = 0o600
REFRESH_MARGIN_S = 120
_OIDC_ENV_PATH = Path.home() / "Dev" / "sanctum-router" / ".env"


class TokenExpiredError(RuntimeError):
    """The token has expired and cannot be refreshed."""


class TokenUnavailableError(RuntimeError):
    """No token source is available."""


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += "=" * padding
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def _jwt_expiry(token: str) -> int | None:
    payload = _decode_jwt_payload(token)
    return payload.get("exp")


def _jwt_expired(token: str, margin: int = REFRESH_MARGIN_S) -> bool:
    exp = _jwt_expiry(token)
    if exp is None:
        return True
    return time.time() + margin >= exp


class TokenProvider(ABC):
    """Abstract token provider with preflight expiry and automatic refresh."""

    @abstractmethod
    def get_token(self) -> str:
        """Return a valid token, refreshing if necessary."""

    @abstractmethod
    def force_refresh(self) -> str:
        """Force a token refresh and return the new token."""


class RouterTokenProvider(TokenProvider):
    """Token provider for Sanctum Router.

    Resolution order:
    1. In-memory cached token from a previous resolution
    2. Explicit env var (SANCTUM_ROUTER_TOKEN / SANCTUM_ROUTER_JWT)
    3. Cache file at ~/.sanctum/router-token-cache.json
    4. OIDC refresh_token grant (from cache's refresh_token)
    5. OIDC client_credentials grant
    """

    def __init__(self, explicit_token: str | None = None) -> None:
        self._explicit_token = explicit_token
        self._current_token: str | None = None
        self._refresh_token: str | None = None
        self._client_id: str | None = None
        self._client_secret: str | None = None

    def _load_oidc_creds(self) -> tuple[str, str]:
        if self._client_id and self._client_secret:
            return self._client_id, self._client_secret

        client_id = os.environ.get("SANCTUM_ROUTER_CLIENT_ID") or os.environ.get("OIDC_CLIENT_ID")
        client_secret = os.environ.get("SANCTUM_ROUTER_CLIENT_SECRET") or os.environ.get(
            "OIDC_CLIENT_SECRET"
        )

        if (not client_id or not client_secret) and _OIDC_ENV_PATH.exists():
            for line in _OIDC_ENV_PATH.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("\"'")
                if k == "oidc_client_id" and not client_id:
                    client_id = v
                elif k == "oidc_client_secret" and not client_secret:
                    client_secret = v

        self._client_id = client_id or ""
        self._client_secret = client_secret or ""
        return self._client_id, self._client_secret

    def _read_cache(self) -> dict[str, Any] | None:
        if not CACHE_FILE.exists():
            return None
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return None

    def _write_cache(self, data: dict[str, Any]) -> None:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(data, indent=2))
        with contextlib.suppress(PermissionError):
            CACHE_FILE.chmod(CACHE_MODE)

    def _do_refresh(self, refresh_token: str) -> dict[str, Any] | None:
        client_id, client_secret = self._load_oidc_creds()
        if not client_id or not client_secret:
            return None
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        try:
            resp = httpx.post(TOKEN_URL, data=data, timeout=15.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _do_client_credentials(self) -> dict[str, Any] | None:
        client_id, client_secret = self._load_oidc_creds()
        if not client_id or not client_secret:
            return None
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "audience": AUDIENCE,
            "scope": SCOPE,
        }
        try:
            resp = httpx.post(TOKEN_URL, data=data, timeout=15.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def get_token(self) -> str:
        if self._current_token and not _jwt_expired(self._current_token):
            return self._current_token

        if self._explicit_token:
            if not _jwt_expired(self._explicit_token):
                self._current_token = self._explicit_token
                return self._current_token
            raise TokenExpiredError(
                "SANCTUM_ROUTER_TOKEN or SANCTUM_ROUTER_JWT is expired. "
                "Set a fresh token in the environment, or unset it so the CLI "
                "uses its cached auto-refreshed token instead."
            )

        cached = self._read_cache()
        if cached:
            token = cached.get("access_token", "")
            if token and not _jwt_expired(token):
                self._current_token = token
                self._refresh_token = cached.get("refresh_token", "")
                return token

            refresh_token = cached.get("refresh_token", "")
            if refresh_token:
                log.info("Router token expired, refreshing via OIDC refresh_token grant...")
                refreshed = self._do_refresh(refresh_token)
                if refreshed:
                    refreshed["refresh_token"] = refreshed.get("refresh_token", refresh_token)
                    self._write_cache(refreshed)
                    self._current_token = refreshed.get("access_token", "")
                    self._refresh_token = refreshed.get("refresh_token", "")
                    return self._current_token

        log.info("No cached Router token, requesting via client_credentials...")
        result = self._do_client_credentials()
        if result:
            result["grant_used"] = "client_credentials"
            self._write_cache(result)
            self._current_token = result.get("access_token", "")
            self._refresh_token = result.get("refresh_token", "")
            return self._current_token

        raise TokenUnavailableError(
            "No Router token available. "
            "Set SANCTUM_ROUTER_TOKEN or configure OIDC credentials "
            "(SANCTUM_ROUTER_CLIENT_ID / SANCTUM_ROUTER_CLIENT_SECRET)."
        )

    def force_refresh(self) -> str:
        if self._refresh_token:
            refreshed = self._do_refresh(self._refresh_token)
            if refreshed:
                refreshed["refresh_token"] = refreshed.get("refresh_token", self._refresh_token)
                self._write_cache(refreshed)
                self._current_token = refreshed.get("access_token", "")
                self._refresh_token = refreshed.get("refresh_token", "")
                return self._current_token

        result = self._do_client_credentials()
        if result:
            result["grant_used"] = "client_credentials"
            self._write_cache(result)
            self._current_token = result.get("access_token", "")
            self._refresh_token = result.get("refresh_token", "")
            return self._current_token

        if self._explicit_token:
            raise TokenUnavailableError(
                "SANCTUM_ROUTER_TOKEN is set but no refresh mechanism is available. "
                "Unset the env var to use cached/auto-refreshed tokens, or configure "
                "OIDC credentials (SANCTUM_ROUTER_CLIENT_ID / SANCTUM_ROUTER_CLIENT_SECRET)."
            )
        raise TokenUnavailableError("Cannot refresh Router token — no OIDC credentials configured.")


def has_router_token_source() -> bool:
    """Check if any Router token source exists without making network calls."""
    if os.getenv("SANCTUM_ROUTER_TOKEN") or os.getenv("SANCTUM_ROUTER_JWT"):
        return True
    if CACHE_FILE.exists():
        return True
    client_id = os.getenv("SANCTUM_ROUTER_CLIENT_ID") or os.getenv("OIDC_CLIENT_ID")
    client_secret = os.getenv("SANCTUM_ROUTER_CLIENT_SECRET") or os.getenv("OIDC_CLIENT_SECRET")
    if client_id and client_secret:
        return True
    return bool(_OIDC_ENV_PATH.exists())
