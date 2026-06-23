"""Test tile locator resolution range validation."""
import pytest
from tilemapservice.models.source import DataSource
from tilemapservice.models.tile import TileRequest
from tilemapservice.services.tile_locator import TileLocator
from tilemapservice.utils.coordinates import TileMatrixSet
from tilemapservice.utils.exceptions import TileNotFoundError


@pytest.fixture
def mock_source_16_18(tmp_path):
    """Create a mock source with zoom levels 16-18 (EPSG:4326)."""
    level_dir = tmp_path / "_alllayers" / "L16"
    level_dir.mkdir(parents=True)
    bundle_file = level_dir / "R0000C0000.bundle"
    bundle_file.write_bytes(b"\x00" * 100)

    tile_matrix_set = TileMatrixSet("source", "EPSG:4326", -180, 90)
    # Set resolutions for levels 16, 17, 18
    tile_matrix_set.resolutions = {
        16: 0.0000107288,  # ~1.19 m/pixel at equator
        17: 0.0000053644,
        18: 0.0000026822,
    }

    source = DataSource(
        name="test-source",
        data_path=tmp_path,
        description="Test source",
        spatial_ref_wkid=4326,
        tile_origin_x=-180,
        tile_origin_y=90,
        tile_size=256,
    )
    source.tile_matrix_set = tile_matrix_set
    source.min_zoom = 16
    source.max_zoom = 18

    return source


def test_geographic_matrix_rejects_zoom_below_range(mock_source_16_18):
    """Test that geographic matrix rejects zoom levels far below the data range."""
    locator = TileLocator()
    # Request zoom 9 (much lower than min_zoom=16)
    request = TileRequest(
        source_name="test-source",
        z=9,
        x=618,
        y=97,
        srs="EPSG:4326",
        matrix="geographic",
        service_type="xyz",
        output_format="png",
    )

    with pytest.raises(TileNotFoundError) as exc_info:
        locator.locate(request, mock_source_16_18)

    assert "分辨率与数据源可用分辨率相差过大" in str(exc_info.value)


def test_geographic_matrix_rejects_zoom_above_range(mock_source_16_18):
    """Test that geographic matrix rejects zoom levels far above the data range."""
    locator = TileLocator()
    # Request zoom 22 (much higher than max_zoom=18)
    request = TileRequest(
        source_name="test-source",
        z=22,
        x=2479155,
        y=388776,
        srs="EPSG:4326",
        matrix="geographic",
        service_type="xyz",
        output_format="png",
    )

    with pytest.raises(TileNotFoundError) as exc_info:
        locator.locate(request, mock_source_16_18)

    assert "分辨率与数据源可用分辨率相差过大" in str(exc_info.value)


def test_geographic_matrix_accepts_zoom_within_range(mock_source_16_18):
    """Test that geographic matrix accepts zoom levels within the data range."""
    locator = TileLocator()
    # Request zoom 16 (within min_zoom=16, max_zoom=18)
    request = TileRequest(
        source_name="test-source",
        z=16,
        x=39582,
        y=6218,
        srs="EPSG:4326",
        matrix="geographic",
        service_type="xyz",
        output_format="png",
    )

    # Should not raise TileNotFoundError for resolution mismatch
    # (may still fail for other reasons like bundle not found, but that's expected)
    try:
        locator.locate(request, mock_source_16_18)
    except TileNotFoundError as e:
        # If it fails, it should NOT be due to resolution mismatch
        assert "分辨率" not in str(e)


def test_source_matrix_resolution_validation_consistent_with_geographic(mock_source_16_18):
    """Test that source matrix has consistent behavior with geographic matrix for out-of-range requests."""
    locator = TileLocator()

    # Request zoom 9 with source matrix (direct mapping, no CRS transform)
    request = TileRequest(
        source_name="test-source",
        z=9,
        x=618,
        y=97,
        srs="EPSG:4326",
        matrix="source",
        service_type="xyz",
        output_format="png",
    )

    # Should fail because level 9 doesn't exist in resolutions dict
    with pytest.raises((TileNotFoundError, ValueError)):
        locator.locate(request, mock_source_16_18)


def test_resolution_ratio_boundary_cases(mock_source_16_18):
    """Test resolution ratio validation at boundary values."""
    locator = TileLocator()

    # Zoom 15: ratio = res(15) / res(16) ≈ 2.0 (should be rejected with 1.5x threshold)
    request_15 = TileRequest(
        source_name="test-source",
        z=15,
        x=19791,
        y=3109,
        srs="EPSG:4326",
        matrix="geographic",
        service_type="xyz",
        output_format="png",
    )

    with pytest.raises(TileNotFoundError) as exc_info:
        locator.locate(request_15, mock_source_16_18)

    assert "分辨率" in str(exc_info.value)

    # Zoom 19: ratio = res(19) / res(18) ≈ 0.5 (should be rejected with 0.67 threshold)
    request_19 = TileRequest(
        source_name="test-source",
        z=19,
        x=316656,
        y=49744,
        srs="EPSG:4326",
        matrix="geographic",
        service_type="xyz",
        output_format="png",
    )

    with pytest.raises(TileNotFoundError) as exc_info:
        locator.locate(request_19, mock_source_16_18)

    assert "分辨率" in str(exc_info.value)
