import pytest
from unittest.mock import Mock

from tilemapservice.services.wmts_service import WmtsService
from tilemapservice.models.wmts import WmtsTileRequest
from tilemapservice.utils.exceptions import InvalidTileRequestError


def test_wmts_service_parse_tilematrixset_webmercator():
    service = WmtsService(tile_service=Mock(), source_manager=Mock())
    matrix_type, crs = service.parse_tilematrixset("WebMercator")
    assert matrix_type == "webmercator"
    assert crs == "EPSG:3857"


def test_wmts_service_parse_tilematrixset_geographic():
    service = WmtsService(tile_service=Mock(), source_manager=Mock())
    matrix_type, crs = service.parse_tilematrixset("Geographic")
    assert matrix_type == "geographic"
    assert crs == "EPSG:4326"


def test_wmts_service_parse_tilematrixset_native():
    service = WmtsService(tile_service=Mock(), source_manager=Mock())
    matrix_type, crs = service.parse_tilematrixset("WebMercator-native")
    assert matrix_type == "source"
    assert crs == "EPSG:3857"


def test_wmts_service_parse_tilematrixset_epsg():
    service = WmtsService(tile_service=Mock(), source_manager=Mock())
    matrix_type, crs = service.parse_tilematrixset("EPSG:4490")
    assert matrix_type == "source"
    assert crs == "EPSG:4490"


def test_wmts_service_validate_native_crs_match():
    source = Mock()
    source.srs = "EPSG:3857"
    source.name = "test"

    service = WmtsService(tile_service=Mock(), source_manager=Mock())
    request = WmtsTileRequest(
        layer="test", style="default", tilematrixset="WebMercator-native",
        tilematrix=10, tilerow=100, tilecol=200,
    )
    service.validate_crs_compatibility(request, source)  # Should not raise


def test_wmts_service_validate_native_crs_mismatch():
    source = Mock()
    source.srs = "EPSG:4326"
    source.name = "test"

    service = WmtsService(tile_service=Mock(), source_manager=Mock())
    request = WmtsTileRequest(
        layer="test", style="default", tilematrixset="WebMercator-native",
        tilematrix=10, tilerow=100, tilecol=200,
    )

    with pytest.raises(InvalidTileRequestError):
        service.validate_crs_compatibility(request, source)


def test_wmts_service_validate_epsg_crs_mismatch():
    source = Mock()
    source.srs = "EPSG:4326"
    source.name = "test"

    service = WmtsService(tile_service=Mock(), source_manager=Mock())
    request = WmtsTileRequest(
        layer="test", style="default", tilematrixset="EPSG:3857",
        tilematrix=10, tilerow=100, tilecol=200,
    )

    with pytest.raises(InvalidTileRequestError):
        service.validate_crs_compatibility(request, source)


def test_wmts_service_parse_tilematrixset_geographic_native():
    service = WmtsService(tile_service=Mock(), source_manager=Mock())
    matrix_type, crs = service.parse_tilematrixset("Geographic-native")
    assert matrix_type == "source"
    assert crs == "EPSG:4326"


def test_wmts_service_parse_tilematrixset_custom_native():
    service = WmtsService(tile_service=Mock(), source_manager=Mock())
    matrix_type, crs = service.parse_tilematrixset("EPSG:4490-native")
    assert matrix_type == "source"
    assert crs == "EPSG:4490"


def test_wmts_service_parse_tilematrixset_unknown():
    service = WmtsService(tile_service=Mock(), source_manager=Mock())
    matrix_type, crs = service.parse_tilematrixset("UnknownMatrix")
    assert matrix_type == "webmercator"
    assert crs == "EPSG:3857"


def test_wmts_service_validate_non_native_crs_no_validation():
    """Non-native TileMatrixSet should not validate CRS compatibility."""
    source = Mock()
    source.srs = "EPSG:4326"
    source.name = "test"

    service = WmtsService(tile_service=Mock(), source_manager=Mock())
    # WebMercator is not a native TileMatrixSet, so no CRS validation should occur
    request = WmtsTileRequest(
        layer="test", style="default", tilematrixset="WebMercator",
        tilematrix=10, tilerow=100, tilecol=200,
    )
    # Should not raise even though source CRS differs
    service.validate_crs_compatibility(request, source)