from tilemapservice.services.cache import TileCache


def test_disabled_cache_is_noop():
    cache = TileCache(enabled=False, max_size=10)
    cache.set("key", b"value")
    assert cache.get("key") is None
    assert cache.size() == 0


def test_enabled_cache_set_and_get():
    cache = TileCache(enabled=True, max_size=10)
    cache.set("key1", b"value1")
    assert cache.get("key1") == b"value1"


def test_lru_eviction_by_entry_count():
    cache = TileCache(enabled=True, max_size=3)
    cache.set("k1", b"v1")
    cache.set("k2", b"v2")
    cache.set("k3", b"v3")
    cache.set("k4", b"v4")
    assert cache.get("k1") is None
    assert cache.get("k4") == b"v4"


def test_clear_and_capacity():
    cache = TileCache(enabled=True, max_size=10)
    cache.set("k1", b"v1")
    assert cache.capacity() == (1, 10, True)
    cache.clear()
    assert cache.capacity() == (0, 10, True)

