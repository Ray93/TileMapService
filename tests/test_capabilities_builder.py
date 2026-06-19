import pytest
from tilemapservice.services.capabilities_builder import CapabilitiesBuilder
from tilemapservice.models.source import DataSource
from tilemapservice.utils.coordinates import TileMatrixSet


def test_capabilities_builder_generate_xml():
    """CapabilitiesBuilder should generate valid WMTS GetCapabilities XML."""
    # Create minimal test source
    source_matrix = TileMatrixSet(
        name="source",
        crs="EPSG:3857",
        origin_x=-20037508.34,
        origin_y=20037508.34,
        resolutions={0: 156543.033928, 1: 78271.516964},
        wmts_identifier="EPSG:3857-native",
    )
    source = DataSource(
        name="test_source",
        data_path="/data/test",
        spatial_ref_wkid=3857,
        bounds=[-20037508.34, -20037508.34, 20037508.34, 20037508.34],
        min_zoom=0,
        max_zoom=1,
        tile_matrix_set=source_matrix,
    )

    builder = CapabilitiesBuilder(
        sources=[source],
        service_url="http://localhost:8000",
    )
    xml = builder.generate()

    assert "<?xml version=" in xml
    assert "<Capabilities" in xml
    assert "xmlns=\"http://www.opengis.net/wmts/1.0\"" in xml
    assert "<ows:ServiceIdentification>" in xml
    assert "<ows:ServiceType>OGC WMTS</ows:ServiceType>" in xml
    assert "<ows:Identifier>test_source</ows:Identifier>" in xml
    assert "<ows:Identifier>WebMercator</ows:Identifier>" in xml


def test_native_geographic_matrix_height_uses_latitude_extent():
    source_matrix = TileMatrixSet(
        name="source",
        crs="EPSG:4326",
        origin_x=-180.0,
        origin_y=90.0,
        resolutions={0: 180.0 / 256},
        wmts_identifier="EPSG:4326-native",
    )
    source = DataSource(
        name="geo",
        data_path="/data/geo",
        spatial_ref_wkid=4326,
        bounds=[-180, -90, 180, 90],
        min_zoom=0,
        max_zoom=0,
        tile_matrix_set=source_matrix,
    )

    xml = CapabilitiesBuilder([source], "http://localhost:8000").generate()

    native_section = xml.split("<ows:Identifier>EPSG:4326-native</ows:Identifier>", 1)[1]
    assert "<MatrixWidth>2</MatrixWidth>" in native_section
    assert "<MatrixHeight>1</MatrixHeight>" in native_section
