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
FORMS_API_BASE = os.getenv("SANCTUM_FORMS_API_BASE", "https://forms.digitalsanctum.com.au/api/v1")
FLOW_API_BASE = os.getenv("SANCTUM_FLOW_API_BASE", "https://flow.digitalsanctum.com.au/api/v1")
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


def set_forms_api_base(base_url: str) -> None:
    global FORMS_API_BASE
    FORMS_API_BASE = base_url.rstrip("/")


def set_flow_api_base(base_url: str) -> None:
    global FLOW_API_BASE
    FLOW_API_BASE = base_url.rstrip("/")


_FORMS_ACCOUNT_ID: str = ""


def set_forms_account_id(account_id: str) -> None:
    global _FORMS_ACCOUNT_ID
    _FORMS_ACCOUNT_ID = account_id


_FLOW_API_KEY: str = ""


def set_flow_api_key(key: str) -> None:
    global _FLOW_API_KEY
    _FLOW_API_KEY = key


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
        except (
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.TimeoutException,
        ) as exc:
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


def _forms_request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    client = httpx.Client(
        base_url=FORMS_API_BASE,
        timeout=_TIMEOUT,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    kwargs.setdefault("headers", {})
    kwargs["headers"]["Authorization"] = f"Bearer {_current_token}"
    kwargs["headers"]["Content-Type"] = "application/json"
    if _FORMS_ACCOUNT_ID:
        kwargs["headers"]["X-Account-Id"] = _FORMS_ACCOUNT_ID

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            r = client.request(method, path, **kwargs)
            if r.status_code not in _RETRY_STATUSES:
                return r
            last_exc = httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
        except (
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.TimeoutException,
        ) as exc:
            last_exc = exc
        if attempt < _MAX_RETRIES - 1:
            wait = 0.5 * (2**attempt)
            log.warning(
                "Forms retry %d/%d for %s %s (%.1fs backoff)",
                attempt + 1,
                _MAX_RETRIES,
                method,
                path,
                wait,
            )
            time.sleep(wait)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Forms request failed: {method} {path}")


def forms_get(path: str, params: dict | None = None) -> Any:
    r = _forms_request("GET", path, params=params)
    _check_upstream(r, "GET", path)
    return r.json()


def forms_post(path: str, json: dict | None = None) -> Any:
    r = _forms_request("POST", path, json=json)
    if r.status_code == 422:
        return {"error": True, "status_code": 422, **r.json()}
    _check_upstream(r, "POST", path)
    return r.json()


def forms_put(path: str, json: dict | None = None) -> Any:
    r = _forms_request("PUT", path, json=json)
    if r.status_code == 422:
        return {"error": True, "status_code": 422, **r.json()}
    _check_upstream(r, "PUT", path)
    return r.json()


def forms_patch(path: str, json: dict | None = None) -> Any:
    r = _forms_request("PATCH", path, json=json)
    _check_upstream(r, "PATCH", path)
    return r.json()


def forms_delete(path: str) -> Any:
    r = _forms_request("DELETE", path)
    _check_upstream(r, "DELETE", path)
    if r.status_code == 204 or not r.content:
        return {"status": "deleted"}
    return r.json()


def _flow_request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    client = httpx.Client(
        base_url=FLOW_API_BASE,
        timeout=_TIMEOUT,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    kwargs.setdefault("headers", {})
    flow_api_key = _FLOW_API_KEY or os.getenv("SANCTUM_FLOW_API_KEY") or os.getenv("FLOW_API_KEY")
    if flow_api_key:
        kwargs["headers"]["X-API-Key"] = flow_api_key
    else:
        kwargs["headers"]["Authorization"] = f"Bearer {_current_token}"
    kwargs["headers"]["Content-Type"] = "application/json"

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            r = client.request(method, path, **kwargs)
            if r.status_code not in _RETRY_STATUSES:
                return r
            last_exc = httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
        except (
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.TimeoutException,
        ) as exc:
            last_exc = exc
        if attempt < _MAX_RETRIES - 1:
            wait = 0.5 * (2**attempt)
            log.warning(
                "Flow retry %d/%d for %s %s (%.1fs backoff)",
                attempt + 1,
                _MAX_RETRIES,
                method,
                path,
                wait,
            )
            time.sleep(wait)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Flow request failed: {method} {path}")


def flow_get(path: str, params: dict | None = None) -> Any:
    r = _flow_request("GET", path, params=params)
    _check_upstream(r, "GET", path)
    return r.json()


def flow_post(path: str, json: dict | None = None, params: dict | None = None) -> Any:
    r = _flow_request("POST", path, json=json, params=params)
    if r.status_code in (400, 409, 422):
        return {"error": True, "status_code": r.status_code, **r.json()}
    _check_upstream(r, "POST", path)
    return r.json()


def flow_patch(path: str, json: dict | None = None, params: dict | None = None) -> Any:
    r = _flow_request("PATCH", path, json=json, params=params)
    if r.status_code in (400, 409, 422):
        return {"error": True, "status_code": r.status_code, **r.json()}
    _check_upstream(r, "PATCH", path)
    return r.json()
