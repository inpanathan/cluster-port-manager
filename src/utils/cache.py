"""Cache abstraction with Redis and in-memory backends.

Provides a CacheStore protocol and two implementations:
- RedisCacheStore for production (uses Redis with JSON serialization)
- InMemoryCacheStore for testing and mock mode
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from src.utils.logger import get_logger

logger = get_logger(__name__)


class CacheStore(Protocol):
    """Protocol for key-value cache stores."""

    def get(self, key: str) -> dict[str, Any] | None: ...

    def set(self, key: str, value: dict[str, Any], *, ttl_seconds: int | None = None) -> None: ...

    def delete(self, key: str) -> None: ...

    def keys(self, pattern: str = "*") -> list[str]: ...


class InMemoryCacheStore:
    """Dict-backed cache for testing. No real TTL enforcement."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    def set(self, key: str, value: dict[str, Any], *, ttl_seconds: int | None = None) -> None:
        self._data[key] = value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def keys(self, pattern: str = "*") -> list[str]:
        if pattern == "*":
            return list(self._data.keys())
        # Simple prefix matching: "chat:*" -> keys starting with "chat:"
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self._data if k.startswith(prefix)]
        return [k for k in self._data if k == pattern]


class RedisCacheStore:
    """Redis-backed cache with JSON serialization and TTL support."""

    def __init__(self, redis_url: str, default_ttl_seconds: int = 604800) -> None:
        import redis as redis_lib

        self._client = redis_lib.Redis.from_url(redis_url, decode_responses=True)
        self._default_ttl = default_ttl_seconds
        logger.info("redis_cache_initialized", url=redis_url.split("@")[-1])

    def get(self, key: str) -> dict[str, Any] | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[arg-type,no-any-return]

    def set(self, key: str, value: dict[str, Any], *, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds or self._default_ttl
        serialized = json.dumps(value, default=str)
        self._client.setex(key, ttl, serialized)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def keys(self, pattern: str = "*") -> list[str]:
        return [k for k in self._client.scan_iter(match=pattern)]  # type: ignore[union-attr]


def create_cache_store(
    backend: str,
    redis_url: str = "",
    default_ttl_days: int = 7,
) -> CacheStore:
    """Factory to create the appropriate cache store.

    Returns InMemoryCacheStore for mock backend, RedisCacheStore otherwise.
    """
    if backend == "mock":
        logger.info("cache_store_created", backend="in_memory")
        return InMemoryCacheStore()
    return RedisCacheStore(
        redis_url=redis_url,
        default_ttl_seconds=default_ttl_days * 86400,
    )
