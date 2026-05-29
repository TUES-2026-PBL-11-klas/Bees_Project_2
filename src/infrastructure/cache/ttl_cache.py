import asyncio
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    """Async-safe in-memory TTL cache."""

    def __init__(self, ttl_seconds: int):
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, _CacheEntry[T]] = {}
        self._lock = asyncio.Lock()

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    async def get(self, key: str) -> T | None:
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= time.monotonic():
                del self._entries[key]
                return None
            return entry.value

    async def set(self, key: str, value: T) -> None:
        async with self._lock:
            self._entries[key] = _CacheEntry(
                value=value,
                expires_at=time.monotonic() + self._ttl_seconds,
            )

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()
