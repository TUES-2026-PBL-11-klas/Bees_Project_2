import asyncio

import pytest

from src.infrastructure.cache.ttl_cache import TTLCache


@pytest.mark.asyncio
async def test_ttl_cache_stores_and_returns_value():
    cache = TTLCache[str](ttl_seconds=60)
    await cache.set("key", "value")
    assert await cache.get("key") == "value"


@pytest.mark.asyncio
async def test_ttl_cache_expires_entries(monkeypatch):
    cache = TTLCache[str](ttl_seconds=1)
    await cache.set("key", "value")

    current = 0.0

    def fake_monotonic():
        return current

    monkeypatch.setattr("src.infrastructure.cache.ttl_cache.time.monotonic", fake_monotonic)

    assert await cache.get("key") == "value"
    current = 2.0
    assert await cache.get("key") is None
