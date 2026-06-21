"""Request statistics."""
from collections import defaultdict
from threading import Lock
from time import time


class RequestStats:
    """Thread-safe request counters.

    Per-source stats are only tracked for known sources (those in the whitelist).
    Unknown sources are grouped under '_unknown' to prevent unbounded memory growth
    from attacker-controlled source/layer names.
    """

    def __init__(self, known_sources: set[str] | None = None):
        self.started_at = time()
        self._lock = Lock()
        self.requests_total = 0
        self.requests_success = 0
        self.requests_failed = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.source_stats: dict[str, dict] = defaultdict(lambda: {"requests": 0, "cache_hits": 0})
        self._known_sources = known_sources or set()

    def record_request(self, success: bool, source: str | None = None) -> None:
        with self._lock:
            self.requests_total += 1
            if success:
                self.requests_success += 1
            else:
                self.requests_failed += 1
            if source:
                key = source if source in self._known_sources else "_unknown"
                self.source_stats[key]["requests"] += 1

    def record_cache(self, hit: bool, source: str | None = None) -> None:
        with self._lock:
            if hit:
                self.cache_hits += 1
                if source:
                    key = source if source in self._known_sources else "_unknown"
                    self.source_stats[key]["cache_hits"] += 1
            else:
                self.cache_misses += 1

    def get_stats(self) -> dict:
        with self._lock:
            cache_total = max(self.cache_hits + self.cache_misses, 1)
            return {
                "uptime": round(time() - self.started_at, 3),
                "requests_total": self.requests_total,
                "requests_success": self.requests_success,
                "requests_failed": self.requests_failed,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_hit_rate": round(self.cache_hits / cache_total, 3),
                "sources": dict(self.source_stats),
            }

