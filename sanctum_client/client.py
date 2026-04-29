"""Synchronous HTTP client for Sanctum Core API.

Used by sanctum-cli. Includes retry with backoff for transient errors.
Authentication via bearer token set by set_api_token().
"""

import logging
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

API_BASE = os.getenv("SANCTUM_API_BASE", "https://core.digitalsanctum.com.au/api")
API_TOKEN = os.getenv("SANCTUM_API_TOKEN", "")

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_RETRIES = 3
_RETRY_STATUSES = {502, 503, 504}

_client: httpx.Client | None = None
_current_token: str = API_TOKEN


def set_api_base(base_url: str) -> None:
    global API_BASE, _client
    API_BASE = base_url.rstrip("/")
    if _client is not None:
        _client.close()
        _client = None


def set_api_token(token: str) -> None:
    global _current_token
    _current_token = token


def get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            base_url=API_BASE,
            timeout=_TIMEOUT,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    client = get_client()
    kwargs.setdefault("headers", {})
    kwargs["headers"]["Authorization"] = f"Bearer {_current_token}"
    kwargs["headers"]["Content-Type"] = "application/json"

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            r = client.request(method, path, **kwargs)
            if r.status_code not in _RETRY_STATUSES:
                return r
            last_exc = httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
        except (httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.PoolTimeout) as exc:
            last_exc = exc
        if attempt < _MAX_RETRIES - 1:
            wait = 0.5 * (2**attempt)
            log.warning(
                "Retry %d/%d for %s %s (%.1fs backoff)",
                attempt + 1,
                _MAX_RETRIES,
                method,
                path,
                wait,
            )
            time.sleep(wait)

    if last_exc:
        raise last_exc
    raise RuntimeError(f"Request failed: {method} {path}")


def _check_upstream(r: httpx.Response, method: str, path: str) -> None:
    if r.status_code in (401, 403):
        token = _current_token
        token_hint = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else "(empty)"
        body = r.text[:200]
        log.error(
            "UPSTREAM %d | %s %s | token=%s | body=%s",
            r.status_code,
            method,
            path,
            token_hint,
            body,
        )
    r.raise_for_status()


_last_headers: dict[str, str] = {}


def get(path: str, params: dict | None = None) -> Any:
    global _last_headers
    r = _request("GET", path, params=params)
    _check_upstream(r, "GET", path)
    _last_headers = dict(r.headers)
    return r.json()


def post(path: str, json: dict | None = None) -> Any:
    r = _request("POST", path, json=json)
    if r.status_code == 422:
        return {"error": True, "status_code": 422, **r.json()}
    _check_upstream(r, "POST", path)
    return r.json()


def put(path: str, json: dict | None = None) -> Any:
    r = _request("PUT", path, json=json)
    if r.status_code == 422:
        return {"error": True, "status_code": 422, **r.json()}
    _check_upstream(r, "PUT", path)
    return r.json()


def patch(path: str, json: dict | None = None) -> Any:
    r = _request("PATCH", path, json=json)
    _check_upstream(r, "PATCH", path)
    return r.json()


def delete(path: str) -> Any:
    r = _request("DELETE", path)
    _check_upstream(r, "DELETE", path)
    if r.status_code == 204 or not r.content:
        return {"status": "deleted"}
    return r.json()
