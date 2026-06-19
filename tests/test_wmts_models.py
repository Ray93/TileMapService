import pytest
from tilemapservice.models.wmts import WmtsTileRequest


def test_wmts_tile_request_creation():
    """WmtsTileRequest should store all WMTS parameters."""
    request = WmtsTileRequest(
        layer="city",
        style="default",
        tilematrixset="WebMercator",
        tilematrix=10,
        tilerow=123,
        tilecol=456,
        format="image/png",
    )
    assert request.layer == "city"
    assert request.style == "default"
    assert request.tilematrixset == "WebMercator"
    assert request.tilematrix == 10
    assert request.tilerow == 123
    assert request.tilecol == 456
    assert request.format == "image/png"


def test_wmts_tile_request_default_format():
    """WmtsTileRequest should have default format."""
    request = WmtsTileRequest(
        layer="city",
        style="default",
        tilematrixset="WebMercator",
        tilematrix=10,
        tilerow=123,
        tilecol=456,
    )
    assert request.format == "image/png"


def test_wmts_tile_request_to_tile_request():
    """WmtsTileRequest should convert to TileRequest."""
    request = WmtsTileRequest(
        layer="city",
        style="default",
        tilematrixset="WebMercator",
        tilematrix=10,
        tilerow=123,
        tilecol=456,
        format="image/png",
    )
    tile_request = request.to_tile_request()
    assert tile_request.source_name == "city"
    assert tile_request.z == 10
    assert tile_request.x == 456
    assert tile_request.y == 123
    assert tile_request.output_format == "png"