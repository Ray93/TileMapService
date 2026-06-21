"""Tests for BundlePool concurrent access and LRU eviction race conditions."""
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tilemapservice.services.bundle_pool import BundlePool


def test_bundle_pool_prevents_eviction_of_in_use_readers(tmp_path):
    """BundlePool must not evict readers that are currently in use.

    This guards against the point #7 race condition: a reader returned by
    get() but not yet locked could be evicted and closed by another thread,
    causing the first thread to read from a closed file handle.
    """
    # Create mock bundle files
    bundles = [tmp_path / f"bundle_{i}.bundle" for i in range(3)]
    for b in bundles:
        b.write_bytes(b'\x00' * 100)  # Minimal mock bundle

    pool = BundlePool(max_size=2)

    # Mock BundleReader to track close calls
    closed_paths = []
    original_close_called = threading.Event()

    def make_mock_reader(path):
        reader = Mock()
        reader.bundle_path = path
        reader.close_called = False

        def track_close():
            reader.close_called = True
            closed_paths.append(path)
            original_close_called.set()

        reader.close = track_close
        return reader

    with patch('tilemapservice.services.bundle_pool.BundleReader', side_effect=make_mock_reader):
        # Thread 1: Acquire bundle_0 and hold reference
        reader_0, lock_0 = pool.get(bundles[0])
        assert reader_0.bundle_path == bundles[0]

        # Thread 2: Fill pool with bundle_1, bundle_2 (should NOT evict bundle_0)
        reader_1, lock_1 = pool.get(bundles[1])
        reader_2, lock_2 = pool.get(bundles[2])  # This would evict bundle_0 in the buggy version

        # bundle_0 should still be in the pool (not evicted while in use)
        assert bundles[0] not in closed_paths, \
            "bundle_0 must not be closed while still referenced"

        # Release bundle_0 (simulate thread 1 finishing)
        pool.release(bundles[0])

        # Now get another bundle to trigger eviction
        bundle_3 = tmp_path / "bundle_3.bundle"
        bundle_3.write_bytes(b'\x00' * 100)
        reader_3, lock_3 = pool.get(bundle_3)

        # Now bundle_0 should be evicted (no longer in use)
        assert bundles[0] in closed_paths, \
            "bundle_0 should be evicted after release"


def test_bundle_pool_acquire_context_manager(tmp_path):
    """BundlePool.acquire() context manager auto-manages references."""
    bundle = tmp_path / "bundle.bundle"
    bundle.write_bytes(b'\x00' * 100)

    pool = BundlePool(max_size=1)

    closed = []

    def make_mock_reader(path):
        reader = Mock()
        reader.bundle_path = path
        reader.close = lambda: closed.append(path)
        return reader

    with patch('tilemapservice.services.bundle_pool.BundleReader', side_effect=make_mock_reader):
        # Use context manager
        with pool.acquire(bundle) as (reader, lock):
            assert reader.bundle_path == bundle
            # Reader should not be evictable while in context
            stats = pool.get_stats()
            assert stats['pool_size'] == 1

        # After exiting context, reader should be releasable
        bundle_2 = tmp_path / "bundle_2.bundle"
        bundle_2.write_bytes(b'\x00' * 100)
        with pool.acquire(bundle_2):
            pass  # bundle should be evicted

        assert bundle in closed, "First bundle should be evicted after release"


def test_bundle_pool_release_without_acquire_is_safe(tmp_path):
    """Calling release() on a non-existent path should not crash."""
    pool = BundlePool(max_size=2)
    fake_path = tmp_path / "nonexistent.bundle"
    pool.release(fake_path)  # Should not raise
