import pytest

from tilemapservice.utils.coordinates import CoordinateTransformer, TileMatrixSet


def test_webmercator_center_uses_meters_not_lonlat():
    tms = TileMatrixSet("webmercator", "EPSG:3857", -20037508.342787, 20037508.342787)
    x, y = tms.tile_center_to_crs(1, 1, 2)
    assert x == pytest.approx(-5009377.085, abs=1)
    assert y == pytest.approx(5009377.085, abs=1)


def test_webmercator_matrix_size_and_bounds_validation():
    tms = TileMatrixSet("webmercator", "EPSG:3857", -20037508.342787, 20037508.342787)
    assert tms.matrix_size(3) == (8, 8)
    with pytest.raises(ValueError, match="tile out of range"):
        tms.validate_tile(3, 8, 0)


def test_geographic_matrix_size_and_tms_flip():
    tms = TileMatrixSet("geographic", "EPSG:4326", -180, 90)
    assert tms.matrix_size(1) == (4, 2)
    assert tms.tms_to_xyz_y(0, 1) == 1
    assert tms.tms_to_xyz_y(1, 1) == 0


def test_source_selects_closest_level_by_resolution():
    tms = TileMatrixSet("source", "EPSG:4326", -180, 90, resolutions={16: 0.0000107, 17: 0.0000053})
    assert tms.select_closest_level(0.000006) == 17


def test_projected_source_matrix_size_for_epsg_3857():
    tms = TileMatrixSet(
        "source",
        "EPSG:3857",
        -20037508.342787,
        20037508.342787,
        resolutions={1: 78271.51696402048},
    )
    assert tms.matrix_size(1) == (2, 2)


def test_geographic_source_matrix_size_for_epsg_4490():
    """EPSG:4490 (CGCS2000, geographic, degree-based) must be supported via
    CRS introspection rather than a hardcoded EPSG check.

    Resolutions are from the real sample-data/4490 Conf.xml. L10 resolution
    0.001373291015625 deg/px -> world is 360x180 deg -> 1024x512 tiles.
    """
    tms = TileMatrixSet(
        "source",
        "EPSG:4490",
        -180.0,
        90.0,
        resolutions={10: 0.0013732910156250004},
    )
    assert tms.matrix_size(10) == (1024, 512)


def test_geographic_source_matrix_size_validates_in_bounds():
    """Source matrix skips x/y validation (lets file lookup handle 404), only validates z."""
    tms = TileMatrixSet(
        "source",
        "EPSG:4490",
        -180.0,
        90.0,
        resolutions={10: 0.0013732910156250004},
    )
    # Should not raise for any x/y (source matrix skips bounds check)
    tms.validate_tile(10, 640, 128)
    tms.validate_tile(10, 1024, 0)
    tms.validate_tile(10, 99999, 99999)
    # Negative z should raise
    with pytest.raises(ValueError, match="z must be non-negative"):
        tms.validate_tile(-1, 0, 0)


def test_transform_point_same_crs_is_identity():
    coord = CoordinateTransformer()
    assert coord.transform_point(37.6, 55.7, "EPSG:4326", "4326") == (37.6, 55.7)


def test_tile_matrix_set_wmts_identifier():
    """TileMatrixSet should have wmts_identifier field."""
    tms = TileMatrixSet(
        name="webmercator",
        crs="EPSG:3857",
        origin_x=-20037508.342787,
        origin_y=20037508.342787,
        wmts_identifier="WebMercator",
    )
    assert tms.wmts_identifier == "WebMercator"


def test_tile_matrix_set_scale_denominators():
    """TileMatrixSet should have scale_denominators for WMTS."""
    tms = TileMatrixSet(
        name="webmercator",
        crs="EPSG:3857",
        origin_x=-20037508.342787,
        origin_y=20037508.342787,
        scale_denominators={0: 559082264.028, 1: 279541132.014},
    )
    assert tms.scale_denominators[0] == 559082264.028


def test_tile_matrix_set_wmts_defaults():
    """WMTS fields should have correct defaults."""
    tms = TileMatrixSet(
        name="webmercator",
        crs="EPSG:3857",
        origin_x=-20037508.342787,
        origin_y=20037508.342787,
    )
    assert tms.wmts_identifier == ""
    assert tms.scale_denominators is None


def test_create_webmercator_matrix_set():
    """Factory function should create standard WebMercator TileMatrixSet."""
    from tilemapservice.utils.coordinates import create_webmercator_matrix_set

    tms = create_webmercator_matrix_set()
    assert tms.name == "webmercator"
    assert tms.crs == "EPSG:3857"
    assert tms.wmts_identifier == "WebMercator"
    assert tms.origin_x == -20037508.342787
    assert tms.origin_y == 20037508.342787
    assert tms.tile_width == 256
    assert tms.tile_height == 256
    assert len(tms.scale_denominators) == 19  # 0-18
    assert tms.scale_denominators[0] == 559082264.0287178


def test_create_geographic_matrix_set():
    """Factory function should create standard Geographic TileMatrixSet."""
    from tilemapservice.utils.coordinates import create_geographic_matrix_set

    tms = create_geographic_matrix_set()
    assert tms.name == "geographic"
    assert tms.crs == "EPSG:4326"
    assert tms.wmts_identifier == "Geographic"
    assert tms.origin_x == -180.0
    assert tms.origin_y == 90.0
    assert tms.tile_width == 256
    assert tms.tile_height == 256
    assert len(tms.scale_denominators) == 19  # 0-18
