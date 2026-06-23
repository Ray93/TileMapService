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
    # Changed to use min_zoom (first level) instead of max_zoom (last level) for better initial view
    assert "return levels.length ? levels[0] : source.min_zoom;" in response.text


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


class TestTileMatrixField:
    """Test tile_matrix field in DataSource.to_dict()."""

    def test_tile_matrix_structure_complete(self):
        """Test tile_matrix has all required fields."""
        from tilemapservice.utils.coordinates import TileMatrixSet

        tile_matrix_set = TileMatrixSet(
            name="webmercator",
            crs="EPSG:3857",
            origin_x=-20037508.342789244,
            origin_y=20037508.342789244,
            tile_width=256,
            tile_height=256,
        )
        source = DataSource(
            name="test",
            data_path=Path("/fake/path"),
            spatial_ref_wkid=3857,
            tile_origin=(-20037508.342787, 20037508.342787),
            tile_size=256,
            min_zoom=0,
            max_zoom=2,
            tile_matrix_set=tile_matrix_set,
        )
        result = source.to_dict()

        assert "tile_matrix" in result
        tm = result["tile_matrix"]

        # Check all required fields exist
        assert "crs" in tm
        assert "is_geographic" in tm
        assert "proj4" in tm
        assert "wkt" in tm
        assert "origin" in tm
        assert "tile_size" in tm
        assert "resolutions" in tm
        assert "min_zoom" in tm
        assert "max_zoom" in tm

        # Check origin structure
        assert "x" in tm["origin"]
        assert "y" in tm["origin"]

    def test_tile_matrix_resolutions_match_expected_values(self):
        """Test resolutions array matches tile_matrix_set.tile_resolution()."""
        from tilemapservice.utils.coordinates import TileMatrixSet

        tile_matrix_set = TileMatrixSet(
            name="webmercator",
            crs="EPSG:3857",
            origin_x=-20037508.342789244,
            origin_y=20037508.342789244,
            tile_width=256,
            tile_height=256,
        )
        source = DataSource(
            name="test",
            data_path=Path("/fake/path"),
            spatial_ref_wkid=3857,
            min_zoom=0,
            max_zoom=2,
            tile_matrix_set=tile_matrix_set,
        )
        result = source.to_dict()

        resolutions = result["tile_matrix"]["resolutions"]

        # Should have 3 levels (0, 1, 2)
        assert len(resolutions) == 3

        # Check each resolution matches tile_resolution(z)
        for i, z in enumerate(range(0, 3)):
            expected = tile_matrix_set.tile_resolution(z)
            assert abs(resolutions[i] - expected) < 1e-6

    def test_tile_matrix_with_geographic_crs(self):
        """Test tile_matrix with geographic CRS (EPSG:4490)."""
        from tilemapservice.utils.coordinates import TileMatrixSet

        tile_matrix_set = TileMatrixSet(
            name="geographic",
            crs="EPSG:4490",
            origin_x=-180.0,
            origin_y=90.0,
            tile_width=256,
            tile_height=256,
        )
        source = DataSource(
            name="test",
            data_path=Path("/fake/path"),
            spatial_ref_wkid=4490,
            tile_origin=(-180.0, 90.0),
            tile_size=256,
            min_zoom=0,
            max_zoom=1,
            tile_matrix_set=tile_matrix_set,
        )
        result = source.to_dict()

        tm = result["tile_matrix"]
        assert tm["crs"] == "EPSG:4490"
        assert tm["is_geographic"] is True
        assert len(tm["resolutions"]) == 2

    def test_tile_info_still_present_backward_compat(self):
        """Test tile_info field is retained for backward compatibility."""
        from tilemapservice.utils.coordinates import TileMatrixSet

        tile_matrix_set = TileMatrixSet(
            name="webmercator",
            crs="EPSG:3857",
            origin_x=-20037508.342789244,
            origin_y=20037508.342789244,
        )
        source = DataSource(
            name="test",
            data_path=Path("/fake/path"),
            spatial_ref_wkid=3857,
            tile_matrix_set=tile_matrix_set,
        )
        result = source.to_dict()

        # tile_info must still be present
        assert "tile_info" in result
        ti = result["tile_info"]
        assert "tile_size" in ti
        assert "tile_origin" in ti
        assert "levels" in ti
        assert "matrix" in ti

        # Both tile_info and tile_matrix should coexist
        assert "tile_matrix" in result

    def test_tile_matrix_without_tile_matrix_set(self):
        """Test tile_matrix when tile_matrix_set is None (resolutions empty)."""
        source = DataSource(
            name="test",
            data_path=Path("/fake/path"),
            spatial_ref_wkid=3857,
            tile_matrix_set=None,
        )
        result = source.to_dict()

        tm = result["tile_matrix"]
        # resolutions should be empty list when tile_matrix_set is None
        assert tm["resolutions"] == []
        # Other fields should still be present
        assert tm["crs"] == "EPSG:3857"
        assert "is_geographic" in tm
        assert "origin" in tm
