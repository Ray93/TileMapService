import pytest

from tilemapservice.models.config import DefaultsConfig, SourceConfig
from tilemapservice.services.source_manager import SourceManager


def test_source_manager_loads_conf_xml_levels(tmp_path):
    (tmp_path / "_alllayers" / "L16").mkdir(parents=True)
    (tmp_path / "_alllayers" / "L16" / "R0000C0000.bundle").write_bytes(b"x")
    (tmp_path / "Conf.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<CacheInfo xmlns="http://www.esri.com/schemas/ArcGIS/10.0">
  <TileCacheInfo>
    <SpatialReference><WKID>4326</WKID></SpatialReference>
    <TileOrigin><X>-180</X><Y>90</Y></TileOrigin>
    <TileCols>256</TileCols><TileRows>256</TileRows>
    <LODInfos><LODInfo><LevelID>16</LevelID><Scale>1</Scale><Resolution>0.0000107288</Resolution></LODInfo></LODInfos>
  </TileCacheInfo>
</CacheInfo>
""",
        encoding="utf-8",
    )
    manager = SourceManager(DefaultsConfig())
    manager.load_sources([SourceConfig(name="city", path=str(tmp_path))])
    source = manager.get("city")
    assert source is not None
    assert source.spatial_ref_wkid == 4326
    assert source.min_zoom == 16
    assert source.max_zoom == 16
    assert source.tile_matrix_set.resolutions[16] == 0.0000107288


def test_source_manager_infers_bounds_from_bundle_names_when_metadata_missing(tmp_path):
    (tmp_path / "L08").mkdir(parents=True)
    (tmp_path / "L08" / "R0080C0080.bundle").write_bytes(b"x")

    manager = SourceManager(DefaultsConfig())
    manager.load_sources([SourceConfig(name="satellite", path=str(tmp_path))])

    source = manager.get("satellite")
    assert source is not None
    assert source.bounds != (-180.0, -90.0, 180.0, 90.0)
    assert source.bounds == pytest.approx((
        0.0,
        -20037508.342789244,
        20037508.342789244,
        0.0,
    ), abs=1e-5)


def test_source_manager_infers_bounds_as_union_across_all_levels(tmp_path):
    (tmp_path / "L02").mkdir(parents=True)
    (tmp_path / "L02" / "R0000C0000.bundle").write_bytes(b"x")
    (tmp_path / "L08").mkdir(parents=True)
    (tmp_path / "L08" / "R0080C0080.bundle").write_bytes(b"x")

    manager = SourceManager(DefaultsConfig())
    manager.load_sources([SourceConfig(name="world", path=str(tmp_path))])

    source = manager.get("world")
    assert source is not None
    assert source.bounds == pytest.approx((
        -20037508.342789244,
        -20037508.342789244,
        20037508.342789244,
        20037508.342789244,
    ), abs=1e-5)
