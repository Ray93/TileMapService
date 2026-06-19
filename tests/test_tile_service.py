from tilemapservice.models.source import DataSource
from tilemapservice.models.tile import TileRequest
from tilemapservice.services.cache import TileCache
from tilemapservice.services.tile_service import TileService
from tilemapservice.utils.coordinates import TileMatrixSet
from tilemapservice.utils.stats import RequestStats
from tests.conftest import make_v2_bundle


class SourceStub:
    def __init__(self, source):
        self.source = source

    def get(self, name):
        return self.source if name == self.source.name else None


def test_tile_service_reads_bundle_and_caches_by_source_level(tmp_path):
    level_dir = tmp_path / "_alllayers" / "L17"
    level_dir.mkdir(parents=True)
    make_v2_bundle(level_dir / "R0000C0000.bundle")
    source = DataSource(
        name="city",
        data_path=tmp_path,
        spatial_ref_wkid=4326,
        tile_matrix_set=TileMatrixSet(
            "source",
            "EPSG:4326",
            -180,
            90,
            resolutions={17: 180.0 / ((1 << 17) * 256)},
        ),
        min_zoom=17,
        max_zoom=17,
    )
    cache = TileCache(enabled=True, max_size=10)
    stats = RequestStats()
    service = TileService(SourceStub(source), cache, stats)

    # First request - should be cache miss
    response = service.get_tile(TileRequest(source_name="city", z=17, x=0, y=0, srs="EPSG:4326", matrix="source"))
    assert response.content_type == "image/jpeg"
    assert response.source_level == 17
    assert response.source_tile_x == 0
    assert response.source_tile_y == 0
    assert cache.get("city:17:0:0:raw") is not None
    assert stats.cache_misses == 1
    assert stats.cache_hits == 0

    # Second request - should be cache hit
    response2 = service.get_tile(TileRequest(source_name="city", z=17, x=0, y=0, srs="EPSG:4326", matrix="source"))
    assert response2.content_type == "image/jpeg"
    assert stats.cache_misses == 1
    assert stats.cache_hits == 1

