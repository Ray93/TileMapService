"""Thread-safe TTL + LRU raw tile cache."""
from threading import Lock
from typing import Optional

from cachetools import TTLCache


class TileCache:
    """A no-op capable cache. max_size is entry count, not bytes."""

    def __init__(self, enabled: bool = True, max_size: int = 1000, ttl: int = 3600):
        self.enabled = enabled
        self.max_size = max_size
        self.ttl = ttl
        self._lock = Lock()
        self._cache: TTLCache[str, bytes] | None = TTLCache(maxsize=max_size, ttl=ttl) if enabled else None

    def get(self, key: str) -> Optional[bytes]:
        if not self.enabled or self._cache is None:
            return None
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: bytes) -> None:
        if not self.enabled or self._cache is None:
            return
        with self._lock:
            self._cache[key] = value

    def clear(self) -> None:
        if not self.enabled or self._cache is None:
            return
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        if not self.enabled or self._cache is None:
            return 0
        with self._lock:
            return len(self._cache)

    def capacity(self) -> tuple[int, int, bool]:
        return self.size(), self.max_size, self.enabled

