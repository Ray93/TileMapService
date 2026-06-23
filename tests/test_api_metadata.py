import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from main import create_app
from tilemapservice.models.config import AppConfig, SourceConfig
from tilemapservice.models.source import DataSource


def test_sources_endpoint_returns_list():
    app = create_app(AppConfig())
    client = TestClient(app)
    response = client.get("/api/sources")
    assert response.status_code == 200
    assert response.json() == {"sources": []}


def test_source_detail_endpoint_returns_source_dict(tmp_path):
    config = AppConfig(sources=[SourceConfig(name="demo", path=str(tmp_path), description="Demo")])
    app = create_app(config)
    with TestClient(app) as client:
        response = client.get("/api/sources/demo")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "demo"
    assert data["description"] == "Demo"


def test_preview_routes_return_html():
    app = create_app(AppConfig())
    client = TestClient(app)
    response = client.get("/preview")
    assert response.status_code == 200
    assert "TileMapService" in response.text


def test_preview_html_contains_source_cards_and_map_preview_behaviour():
    app = create_app(AppConfig())
    client = TestClient(app)

    response = client.get("/preview")

    assert response.status_code == 200
    html = response.text
    assert 'id="source-list"' in html
    assert 'href="/preview/' in html
    assert 'id="map-view"' in html
    assert "renderSourceCards" in html
    assert "renderMapPreview" in html


def test_preview_html_uses_leaflet_to_fit_data_bounds_and_draw_dashed_boundary():
    app = create_app(AppConfig())
    client = TestClient(app)

    response = client.get("/preview/demo")

    assert response.status_code == 200
    html = response.text
    assert "leaflet.css" in html
    assert "leaflet.js" in html
    assert "initializeLeafletMap" in html
    assert 'L.map("map-canvas"' in html
    assert "L.tileLayer" in html
    assert "fitLeafletMapToSourceBounds" in html
    assert ".fitBounds(" in html
    assert "L.rectangle" in html
    assert "dashArray" in html
    assert "matrix=source" in html


def test_preview_html_starts_at_highest_available_source_zoom():
    app = create_app(AppConfig())
    client = TestClient(app)

    response = client.get("/preview/demo")

    assert response.status_code == 200
    assert "return levels.length ? levels[levels.length - 1] : source.max_zoom;" in response.text


def test_preview_html_has_large_workspace_layout_and_address_switcher():
    app = create_app(AppConfig())
    client = TestClient(app)

    response = client.get("/preview/demo")

    assert response.status_code == 200
    html = response.text
    assert "map-layout" in html
    assert "grid-template-columns: 1fr 500px" in html
    assert 'id="address-mode"' in html
    assert "SOURCE MATRIX" in html
    assert "WEBXYZ" in html
    assert "WEBTMS" in html
    assert "GEO XYZ" in html
    assert "buildAddressModes" in html
    assert "switchAddressMode" in html
    assert "copy-current-url" in html


class TestCRSDefinition:
    """Test _build_crs_definition() helper method."""

    def test_geographic_crs(self):
        """Test geographic CRS (EPSG:4490) returns is_geographic=True."""
        source = DataSource(
            name="test",
            data_path=Path("/fake/path"),
            spatial_ref_wkid=4490,
        )
        crs_def = source._build_crs_definition()

        assert crs_def["is_geographic"] is True
        assert crs_def["proj4"] is not None
        assert "+proj=longlat" in crs_def["proj4"]
        assert crs_def["wkt"] is not None

    def test_projected_crs(self):
        """Test projected CRS (EPSG:32650) returns is_geographic=False."""
        source = DataSource(
            name="test",
            data_path=Path("/fake/path"),
            spatial_ref_wkid=32650,
        )
        crs_def = source._build_crs_definition()

        assert crs_def["is_geographic"] is False
        assert crs_def["proj4"] is not None
        assert "+proj=utm" in crs_def["proj4"]
        assert crs_def["wkt"] is not None

    def test_invalid_wkid(self):
        """Test invalid WKID (99999) returns all None, no exception."""
        source = DataSource(
            name="test",
            data_path=Path("/fake/path"),
            spatial_ref_wkid=99999,
        )
        crs_def = source._build_crs_definition()

        assert crs_def["is_geographic"] is None
        assert crs_def["proj4"] is None
        assert crs_def["wkt"] is None
