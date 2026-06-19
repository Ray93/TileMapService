"""Sharded TTL + LRU cache."""
from threading import Lock
from typing import Optional
from cachetools import TTLCache

class ShardedTileCache:
    def __init__(self, enabled=True, max_size=1000, ttl=3600, num_shards=16):
        self.enabled = enabled
        self.num_shards = num_shards
        self.max_size = max_size
        self.shard_size = max_size // num_shards
        self._shards = [TTLCache(maxsize=self.shard_size, ttl=ttl) for _ in range(num_shards)] if enabled else []
        self._locks = [Lock() for _ in range(num_shards)] if enabled else []

    def _get_shard(self, key: str):
        if not self.enabled:
            return None, Lock()
        idx = hash(key) % self.num_shards
        return self._shards[idx], self._locks[idx]

    def get(self, key: str) -> Optional[bytes]:
        if not self.enabled:
            return None
        cache, lock = self._get_shard(key)
        if cache is None:
            return None
        with lock:
            return cache.get(key)

    def set(self, key: str, value: bytes):
        if not self.enabled:
            return
        cache, lock = self._get_shard(key)
        if cache is None:
            return
        with lock:
            cache[key] = value

    def clear(self):
        if not self.enabled:
            return
        for cache, lock in zip(self._shards, self._locks):
            with lock:
                cache.clear()

    def size(self) -> int:
        if not self.enabled:
            return 0
        total = 0
        for cache, lock in zip(self._shards, self._locks):
            with lock:
                total += len(cache)
        return total

    def capacity(self):
        return self.size(), self.max_size, self.enabled
