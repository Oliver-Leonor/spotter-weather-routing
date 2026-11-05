"""Small thread-safe in-process TTL cache.

Used to avoid repeating identical provider calls. On serverless hosting it lives only as long as
the warm instance does, which is enough to cover a user adjusting one trip.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Hashable
from typing import Any


class TTLCache:
    def __init__(
        self,
        ttl_seconds: float,
        max_entries: int = 4096,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[Hashable, tuple[float, Any]] = {}  # key -> (expires_at, value)

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= self._clock():
                del self._entries[key]
                return None
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            now = self._clock()
            self._entries.pop(key, None)
            if len(self._entries) >= self._max_entries:
                self._evict(now)
            self._entries[key] = (now + self._ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def _evict(self, now: float) -> None:
        """Make room: drop everything expired, then the oldest entries if still full."""
        for key in [k for k, (expires_at, _) in self._entries.items() if expires_at <= now]:
            del self._entries[key]
        while len(self._entries) >= self._max_entries:
            del self._entries[next(iter(self._entries))]
