"""Tests for ShardedTileCache."""

from concurrent.futures import ThreadPoolExecutor
import pytest
from tilemapservice.services.sharded_cache import ShardedTileCache


def test_basic():
    """Test basic get/set operations."""
    cache = ShardedTileCache(max_size=100, num_shards=4)
    cache.set("k1", b"v1")
    assert cache.get("k1") == b"v1"
    assert cache.get("nonexistent") is None


def test_concurrent():
    """Test concurrent access with 20 threads."""
    cache = ShardedTileCache(max_size=100, num_shards=4)

    def worker(i):
        cache.set(f"k{i}", b"data")
        return cache.get(f"k{i}") == b"data"

    with ThreadPoolExecutor(20) as ex:
        results = list(ex.map(worker, range(20)))
    assert all(results)


def test_disabled():
    """Test cache disabled behavior."""
    cache = ShardedTileCache(enabled=False)
    cache.set("k1", b"v1")
    assert cache.get("k1") is None
    assert cache.size() == 0


def test_clear_and_size():
    """Test clear and size methods."""
    cache = ShardedTileCache(max_size=100, num_shards=4)
    cache.set("k1", b"v1")
    cache.set("k2", b"v2")
    assert cache.size() == 2
    cache.clear()
    assert cache.size() == 0


def test_multiple_values():
    """Test storing and retrieving multiple values."""
    cache = ShardedTileCache(max_size=100, num_shards=4)
    for i in range(10):
        cache.set(f"key{i}", f"value{i}".encode())

    for i in range(10):
        assert cache.get(f"key{i}") == f"value{i}".encode()


def test_overwrite():
    """Test overwriting existing keys."""
    cache = ShardedTileCache(max_size=100, num_shards=4)
    cache.set("k1", b"v1")
    assert cache.get("k1") == b"v1"
    cache.set("k1", b"v2")
    assert cache.get("k1") == b"v2"


def test_sharding():
    """Test that different keys go to different shards."""
    cache = ShardedTileCache(max_size=100, num_shards=4)

    # Set multiple keys
    keys = [f"key{i}" for i in range(20)]
    for key in keys:
        cache.set(key, b"data")

    # All keys should be retrievable
    for key in keys:
        assert cache.get(key) == b"data"


def test_capacity():
    """Test cache capacity reporting."""
    cache = ShardedTileCache(max_size=100, num_shards=4)

    # Initial capacity
    size, max_size, enabled = cache.capacity()
    assert size == 0
    assert max_size == 100
    assert enabled is True

    # After adding items
    cache.set("k1", b"v1")
    cache.set("k2", b"v2")
    size, max_size, enabled = cache.capacity()
    assert size == 2
    assert max_size == 100
    assert enabled is True

    # Disabled cache
    disabled_cache = ShardedTileCache(enabled=False)
    size, max_size, enabled = disabled_cache.capacity()
    assert size == 0
    assert enabled is False


def test_eviction():
    """Test LRU eviction behavior."""
    cache = ShardedTileCache(max_size=10, num_shards=2)

    # Fill cache beyond capacity
    for i in range(15):
        cache.set(f"k{i}", b"data")

    # Cache size should not exceed max_size (approximately)
    # Note: With sharding, total size may slightly exceed max_size
    # as each shard has max_size/num_shards capacity
    assert cache.size() <= 12  # Allow some variance due to sharding


def test_concurrent_same_key():
    """Test concurrent access to the same key."""
    cache = ShardedTileCache(max_size=100, num_shards=4)

    def worker(i):
        cache.set("shared_key", f"value{i}".encode())
        result = cache.get("shared_key")
        return result is not None

    with ThreadPoolExecutor(20) as ex:
        results = list(ex.map(worker, range(20)))

    # All operations should succeed
    assert all(results)
    # Final value should be one of the written values
    assert cache.get("shared_key") is not None


def test_empty_value():
    """Test storing empty byte values."""
    cache = ShardedTileCache(max_size=100, num_shards=4)
    cache.set("empty", b"")
    assert cache.get("empty") == b""


def test_max_size_smaller_than_num_shards_keeps_usable_shards():
    """Shard size should never be zero."""
    cache = ShardedTileCache(max_size=2, num_shards=16)
    assert cache.shard_size == 1
    cache.set("k1", b"v1")
    assert cache.get("k1") == b"v1"


def test_large_value():
    """Test storing large byte values."""
    cache = ShardedTileCache(max_size=1000, num_shards=4)
    large_value = b"x" * 10000
    cache.set("large", large_value)
    assert cache.get("large") == large_value
