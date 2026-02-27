"""Unit tests for the cache abstraction."""

from __future__ import annotations

from datetime import datetime

from src.utils.cache import InMemoryCacheStore


def test_set_and_get() -> None:
    cache = InMemoryCacheStore()
    cache.set("key1", {"name": "test", "value": 42})
    result = cache.get("key1")
    assert result is not None
    assert result["name"] == "test"
    assert result["value"] == 42


def test_get_missing_returns_none() -> None:
    cache = InMemoryCacheStore()
    assert cache.get("nonexistent") is None


def test_delete() -> None:
    cache = InMemoryCacheStore()
    cache.set("key1", {"data": "value"})
    cache.delete("key1")
    assert cache.get("key1") is None


def test_keys_all() -> None:
    cache = InMemoryCacheStore()
    cache.set("chat:1", {"id": "1"})
    cache.set("chat:2", {"id": "2"})
    cache.set("interview:1", {"id": "1"})
    keys = cache.keys()
    assert len(keys) == 3


def test_keys_prefix_pattern() -> None:
    cache = InMemoryCacheStore()
    cache.set("chat:1", {"id": "1"})
    cache.set("chat:2", {"id": "2"})
    cache.set("interview:1", {"id": "1"})
    chat_keys = cache.keys("chat:*")
    assert len(chat_keys) == 2
    assert all(k.startswith("chat:") for k in chat_keys)


def test_datetime_serialization() -> None:
    cache = InMemoryCacheStore()
    now = datetime.utcnow()
    cache.set("key1", {"created": now.isoformat(), "nested": {"ts": now.isoformat()}})
    result = cache.get("key1")
    assert result is not None
    assert result["created"] == now.isoformat()
