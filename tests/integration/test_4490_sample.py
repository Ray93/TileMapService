"""Integration tests for non-standard geographic CRS (EPSG:4490 / CGCS2000).

These verify the fix for point #7 (v2 doc item #5): source matrix_size must
work for geographic CRS beyond the hardcoded EPSG:4326/3857.

A minimal fixture (one V1 bundle at L06 + Conf.xml + conf.cdi) is committed
under tests/fixtures/4490 so these run in CI without external sample data.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import create_app
from tilemapservice.models.config import AppConfig, SourceConfig, DefaultsConfig
from tilemapservice.services.source_manager import SourceManager

pytestmark = pytest.mark.integration

FIXTURE_4490 = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "4490"


def test_4490_source_loads_with_correct_metadata():
    manager = SourceManager(DefaultsConfig())
    manager.load_sources([SourceConfig(name="cgcs2000", path=str(FIXTURE_4490))])
    src = manager.get("cgcs2000")
    assert src.srs == "EPSG:4490"
    assert src.min_zoom == 6
    assert src.max_zoom == 6
    # Bounds come from conf.cdi (China region)
    assert src.bounds[0] == pytest.approx(89.371356, abs=1e-4)
    assert src.bounds[2] == pytest.approx(122.34375, abs=1e-4)
    assert src.tile_matrix_set.crs == "EPSG:4490"


def test_4490_source_matrix_size_computed_from_resolution():
    """matrix_size() must not raise for EPSG:4490; L06 -> 64x32."""
    manager = SourceManager(DefaultsConfig())
    manager.load_sources([SourceConfig(name="cgcs2000", path=str(FIXTURE_4490))])
    tms = manager.get("cgcs2000").tile_matrix_set
    assert tms.matrix_size(6) == (64, 32)


def test_4490_api_serves_real_tile():
    """End-to-end: a real 4490 tile is served via /tiles with matrix=source.

    L06 bundle R0000C0000 contains a tile at global row=9, col=47.
    """
    app = create_app(AppConfig(sources=[SourceConfig(name="cgcs2000", path=str(FIXTURE_4490))]))
    with TestClient(app) as client:
        response = client.get(
            "/tiles/cgcs2000/crs/epsg:4490/6/47/9.png?matrix=source"
        )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
