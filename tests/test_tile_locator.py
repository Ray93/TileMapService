from pathlib import Path

from tilemapservice.models.source import DataSource
from tilemapservice.models.tile import TileRequest
from tilemapservice.services.tile_locator import TileLocator
from tilemapservice.utils.coordinates import TileMatrixSet


def test_locator_uses_source_level_instead_of_blind_request_z(tmp_path):
    (tmp_path / "_alllayers" / "L17").mkdir(parents=True)
    source_tms = TileMatrixSet(
        name="source",
        crs="EPSG:4326",
        origin_x=-180,
        origin_y=90,
        resolutions={16: 0.0000107288, 17: 0.0000053644, 18: 0.0000026822},
    )
    source = DataSource(
        name="city",
        data_path=tmp_path,
        spatial_ref_wkid=4326,
        tile_origin=(-180, 90),
        min_zoom=16,
        max_zoom=18,
        tile_matrix_set=source_tms,
    )
    request = TileRequest(
        source_name="city",
        z=17,
        x=100000,
        y=50000,
        srs="EPSG:4326",
        matrix="geographic"
    )
    location = TileLocator().locate(request, source)
    assert location.source_level == 17
    assert location.source_tile_x >= 0
    assert location.source_tile_y >= 0
    assert location.bundle_path.parent.name == "L17"


def test_locator_rejects_mismatched_crs_and_matrix(tmp_path):
    source = DataSource(
        name="city",
        data_path=tmp_path,
        spatial_ref_wkid=4326,
        tile_matrix_set=TileMatrixSet("source", "EPSG:4326", -180, 90, resolutions={0: 1}),
    )
    request = TileRequest(
        source_name="city",
        z=0,
        x=0,
        y=0,
        srs="EPSG:4326",
        matrix="webmercator"
    )
    try:
        TileLocator().locate(request, source)
    except Exception as exc:
        assert exc.__class__.__name__ == "InvalidTileRequestError"
    else:
        raise AssertionError("expected InvalidTileRequestError")

