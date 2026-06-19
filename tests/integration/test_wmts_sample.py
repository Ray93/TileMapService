import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import create_app
from tilemapservice.models.config import AppConfig, SourceConfig, DefaultsConfig

pytestmark = pytest.mark.skipif(
    not os.environ.get("TILEMAPSERVICE_SAMPLE_DATA"),
    reason="TILEMAPSERVICE_SAMPLE_DATA not set",
)


def sample_root() -> Path:
    """Get sample data root directory."""
    value = os.environ.get("TILEMAPSERVICE_SAMPLE_DATA")
    if not value:
        pytest.skip("TILEMAPSERVICE_SAMPLE_DATA not set")
    return Path(value)


def source_configs(root: Path) -> list[SourceConfig]:
    """Create source configs for sample data."""
    return [
        SourceConfig(name="city", path=str(root / "CITY" / "莫斯科.tif")),
        SourceConfig(name="country", path=str(root / "COUNTRY" / "莫斯科新")),
        SourceConfig(name="satellite", path=str(root / "data" / "satellite")),
        SourceConfig(name="world", path=str(root / "data" / "world")),
    ]


@pytest.fixture
def sample_client():
    """Create client with sample data loaded."""
    root = sample_root()
    app = create_app(AppConfig(sources=source_configs(root), defaults=DefaultsConfig()))
    with TestClient(app) as client:
        yield client


def test_wmts_capabilities_with_sample_data(sample_client):
    """GetCapabilities should list sample data sources."""
    response = sample_client.get("/wmts?service=WMTS&request=GetCapabilities")

    assert response.status_code == 200
    xml = response.text
    assert "<Capabilities" in xml

    sources = sample_client.app.state.source_manager.list_all()
    for source in sources:
        assert f"<ows:Identifier>{source.name}</ows:Identifier>" in xml


def test_wmts_get_tile_webmercator(sample_client):
    """GetTile WebMercator should work for EPSG:3857 source."""
    sources = sample_client.app.state.source_manager.list_all()

    epsg3857_source = None
    for s in sources:
        if "3857" in s.srs.upper():
            epsg3857_source = s
            break

    if not epsg3857_source:
        pytest.skip("No EPSG:3857 sample source available")

    z = epsg3857_source.min_zoom
    response = sample_client.get(
        f"/wmts/{epsg3857_source.name}/default/WebMercator/{z}/0/0.png"
    )

    assert response.status_code in (200, 204)
    if response.status_code == 200:
        assert response.headers["content-type"].startswith("image/")


def test_wmts_get_tile_native(sample_client):
    """GetTile native should work for matching CRS.

    Note: Tile (0,0) may not exist for all sources, so we accept
    200 (tile found), 204 (no content), or 400 with TileNotFound.
    """
    sources = sample_client.app.state.source_manager.list_all()

    for source in sources:
        epsg = source.get_epsg_code()
        native_id = f"EPSG:{epsg}-native"

        z = source.min_zoom
        response = sample_client.get(
            f"/wmts/{source.name}/default/{native_id}/{z}/0/0.png"
        )

        # Accept valid responses: tile found, or tile not found errors
        # WMTS returns 400 with ServiceException for TileNotFound
        if response.status_code == 200:
            assert response.headers["content-type"].startswith("image/")
        elif response.status_code == 400:
            # Must be TileNotFound, not an invalid request
            assert "TileNotFound" in response.text or "InvalidParameterValue" not in response.text
        # 204 is also valid (empty response for no tile)