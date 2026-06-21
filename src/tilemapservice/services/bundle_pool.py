"""Bundle file handle connection pool with LRU eviction."""
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Generator

from tilemapservice.readers.bundle_reader import BundleReader


class BundlePool:
    """Thread-safe LRU pool for Bundle file handles.

    Each BundleReader is protected by its own lock to ensure thread-safe
    file operations (seek/read) when the same Bundle is accessed concurrently.

    Reference counting prevents eviction of in-use readers: a reader returned
    by get() increments its refcount, and must be released via release() or
    the acquire() context manager to decrement it. LRU eviction skips readers
    with refcount > 0.
    """

    def __init__(self, max_size: int = 50):
        self._pool: dict[Path, BundleReader] = {}
        self._reader_locks: dict[Path, Lock] = {}  # Per-reader locks
        self._refcounts: dict[Path, int] = {}  # Reference counts
        self._lru: list[Path] = []
        self._lock = Lock()  # Pool management lock
        self._max_size = max_size
        self._stats = {'hits': 0, 'misses': 0, 'evictions': 0}

    def get(self, bundle_path: Path) -> tuple[BundleReader, Lock]:
        """Get or create BundleReader with its lock, updating LRU.

        Increments the reference count for the returned reader. Caller must
        call release() after use, or use the acquire() context manager.

        Returns:
            tuple: (BundleReader, Lock) - The reader and its associated lock.
                   Caller must acquire the lock before calling reader methods.
        """
        with self._lock:
            if bundle_path in self._pool:
                self._stats['hits'] += 1
                self._lru.remove(bundle_path)
                self._lru.append(bundle_path)
                self._refcounts[bundle_path] += 1
                return self._pool[bundle_path], self._reader_locks[bundle_path]

            self._stats['misses'] += 1
            reader = BundleReader(bundle_path)
            reader_lock = Lock()
            self._pool[bundle_path] = reader
            self._reader_locks[bundle_path] = reader_lock
            self._refcounts[bundle_path] = 1  # Initial reference
            self._lru.append(bundle_path)

            # Evict LRU readers that are not in use (refcount == 0)
            while len(self._pool) > self._max_size:
                evicted = False
                for evict_path in self._lru:
                    if self._refcounts[evict_path] == 0:
                        self._lru.remove(evict_path)
                        self._pool[evict_path].close()
                        del self._pool[evict_path]
                        del self._reader_locks[evict_path]
                        del self._refcounts[evict_path]
                        self._stats['evictions'] += 1
                        evicted = True
                        break
                if not evicted:
                    # All readers are in use, cannot evict
                    break

            return reader, reader_lock

    def release(self, bundle_path: Path) -> None:
        """Decrement reference count for a bundle reader.

        Safe to call even if the path is not in the pool.
        """
        with self._lock:
            if bundle_path in self._refcounts:
                self._refcounts[bundle_path] -= 1

    @contextmanager
    def acquire(self, bundle_path: Path) -> Generator[tuple[BundleReader, Lock], None, None]:
        """Context manager for acquiring and auto-releasing a bundle reader.

        Usage:
            with pool.acquire(path) as (reader, lock):
                with lock:
                    data = reader.get_tile(row, col)
        """
        reader, lock = self.get(bundle_path)
        try:
            yield reader, lock
        finally:
            self.release(bundle_path)

    def close_all(self) -> None:
        """Close all Bundle readers."""
        with self._lock:
            for reader in self._pool.values():
                reader.close()
            self._pool.clear()
            self._reader_locks.clear()
            self._refcounts.clear()
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
