import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import create_app
from tilemapservice.models.config import AppConfig, SourceConfig
from tilemapservice.models.config import DefaultsConfig
from tilemapservice.readers.bundle_reader import BundleReader
from tilemapservice.services.source_manager import SourceManager

pytestmark = pytest.mark.integration


def sample_root() -> Path:
    value = os.environ.get("TILEMAPSERVICE_SAMPLE_DATA")
    if not value:
        pytest.skip("TILEMAPSERVICE_SAMPLE_DATA not set")
    return Path(value)


def test_sample_data_root_exists():
    root = sample_root()
    assert root.exists()


def source_configs(root: Path) -> list[SourceConfig]:
    return [
        SourceConfig(name="city", path=str(root / "CITY" / "莫斯科.tif")),
        SourceConfig(name="country", path=str(root / "COUNTRY" / "莫斯科新")),
        SourceConfig(name="satellite", path=str(root / "data" / "satellite")),
        SourceConfig(name="world", path=str(root / "data" / "world")),
    ]


def test_sample_data_sources_load_with_expected_levels():
    root = sample_root()
    manager = SourceManager(DefaultsConfig())
    manager.load_sources(source_configs(root))
    assert manager.count() == 4
    assert manager.get("city").srs == "EPSG:4326"
    assert manager.get("city").min_zoom == 16
    assert manager.get("city").max_zoom == 18
    assert manager.get("country").min_zoom == 13
    assert manager.get("satellite").max_zoom == 16
    assert manager.get("world").min_zoom == 1


def test_sample_data_world_and_satellite_bounds_cover_low_zoom_global_tiles():
    root = sample_root()
    manager = SourceManager(DefaultsConfig())
    manager.load_sources(source_configs(root))

    assert manager.get("satellite").bounds == pytest.approx(
        (-20037508.342789244, -20037508.342789244, 20037508.342789244, 20037508.342789244),
        abs=1e-5,
    )
    assert manager.get("world").bounds == pytest.approx(
        (-20037508.342789244, -20037508.342789244, 20037508.342789244, 20037508.342789244),
        abs=1e-5,
    )


def test_sample_data_real_v2_and_v1_bundle_reads():
    root = sample_root()
    city_bundle = root / "CITY" / "莫斯科.tif" / "_alllayers" / "L16" / "R3000C13480.bundle"
    with BundleReader(city_bundle) as reader:
        tile = reader.get_tile(88, 110)
        assert reader.is_v1 is False
        assert tile is not None
        assert tile.startswith(b"\x89PNG")

    world_bundle = root / "data" / "world" / "L01" / "R0000C0000.bundle"
    with BundleReader(world_bundle) as reader:
        tile = reader.get_tile(0, 0)
        assert reader.is_v1 is True
        assert tile is not None
        assert tile.startswith(b"\x89PNG")


def test_sample_data_api_serves_real_city_and_world_tiles():
    root = sample_root()
    app = create_app(AppConfig(sources=source_configs(root)))
    with TestClient(app) as client:
        city = client.get("/tiles/city/crs/epsg:4326/16/79086/12376.png?matrix=source")
        world = client.get("/tiles/world/crs/epsg:3857/1/0/0.png?matrix=source")
    assert city.status_code == 200
    assert city.headers["content-type"] == "image/png"
    assert city.content.startswith(b"\x89PNG")
    assert world.status_code == 200
    assert world.headers["content-type"] == "image/png"
    assert world.content.startswith(b"\x89PNG")
