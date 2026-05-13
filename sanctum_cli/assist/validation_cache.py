"""TTL-based in-memory cache for Router validation results."""

from __future__ import annotations

import time
from collections.abc import Hashable
from typing import Any


class ValidationCache:
    """Per-process TTL cache for parameter normalization results.

    Cache key: (domain, action, frozenset(sorted(param_keys)), calling_agent)
    TTL: 300s for read operations, 60s for write operations.
    """

    def __init__(self) -> None:
        self._store: dict[Hashable, _CacheEntry] = {}

    def get(self, key: Hashable) -> dict[str, Any] | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.params

    def set(self, key: Hashable, params: dict[str, Any], *, is_read: bool = True) -> None:
        ttl = 300.0 if is_read else 60.0
        self._store[key] = _CacheEntry(
            params=params,
            expires_at=time.monotonic() + ttl,
        )

    def clear(self) -> None:
        self._store.clear()

    def _sweep_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for k in expired:
            del self._store[k]

    @property
    def size(self) -> int:
        self._sweep_expired()
        return len(self._store)


class _CacheEntry:
    def __init__(self, params: dict[str, Any], expires_at: float) -> None:
        self.params = params
        self.expires_at = expires_at


def build_cache_key(
    domain: str,
    action: str,
    params: dict[str, Any],
    calling_agent: str | None,
) -> tuple:
    return (
        domain,
        action,
        frozenset(sorted(params.keys())),
        calling_agent,
    )


_global_cache = ValidationCache()


def get_validation_cache() -> ValidationCache:
    return _global_cache
