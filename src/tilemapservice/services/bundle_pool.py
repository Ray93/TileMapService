"""Bundle file handle connection pool with LRU eviction."""
from pathlib import Path
from threading import Lock
from tilemapservice.readers.bundle_reader import BundleReader


class BundlePool:
    """Thread-safe LRU pool for Bundle file handles.

    Each BundleReader is protected by its own lock to ensure thread-safe
    file operations (seek/read) when the same Bundle is accessed concurrently.
    """

    def __init__(self, max_size: int = 50):
        self._pool: dict[Path, BundleReader] = {}
        self._reader_locks: dict[Path, Lock] = {}  # Per-reader locks
        self._lru: list[Path] = []
        self._lock = Lock()  # Pool management lock
        self._max_size = max_size
        self._stats = {'hits': 0, 'misses': 0, 'evictions': 0}

    def get(self, bundle_path: Path) -> tuple[BundleReader, Lock]:
        """Get or create BundleReader with its lock, updating LRU.

        Returns:
            tuple: (BundleReader, Lock) - The reader and its associated lock.
                   Caller must acquire the lock before calling reader methods.
        """
        with self._lock:
            if bundle_path in self._pool:
                self._stats['hits'] += 1
                self._lru.remove(bundle_path)
                self._lru.append(bundle_path)
                return self._pool[bundle_path], self._reader_locks[bundle_path]

            self._stats['misses'] += 1
            reader = BundleReader(bundle_path)
            reader_lock = Lock()
            self._pool[bundle_path] = reader
            self._reader_locks[bundle_path] = reader_lock
            self._lru.append(bundle_path)

            while len(self._pool) > self._max_size:
                evict = self._lru.pop(0)
                self._pool[evict].close()
                del self._pool[evict]
                del self._reader_locks[evict]
                self._stats['evictions'] += 1

            return reader, reader_lock

    def close_all(self) -> None:
        """Close all Bundle readers."""
        with self._lock:
            for reader in self._pool.values():
                reader.close()
            self._pool.clear()
            self._reader_locks.clear()
            self._lru.clear()

    def get_stats(self) -> dict:
        """Get pool statistics."""
        with self._lock:
            total = self._stats['hits'] + self._stats['misses']
            return {
                'pool_size': len(self._pool),
                'max_size': self._max_size,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'evictions': self._stats['evictions'],
                'hit_rate': f"{self._stats['hits']/total:.2%}" if total > 0 else "0%"
            }
