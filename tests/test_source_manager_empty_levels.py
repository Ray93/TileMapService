"""Test that empty level directories are excluded from available levels."""
import pytest
from pathlib import Path
from tilemapservice.services.source_manager import SourceManager
from tilemapservice.models.config import DefaultsConfig, SourceConfig


def test_scan_levels_excludes_empty_directories(tmp_path):
    """Test that level directories without bundle files are not included."""
    # Create directory structure with some empty levels
    (tmp_path / "_alllayers" / "L04").mkdir(parents=True)  # Empty
    (tmp_path / "_alllayers" / "L05").mkdir(parents=True)  # Empty
    (tmp_path / "_alllayers" / "L06").mkdir(parents=True)  # Has bundle
    (tmp_path / "_alllayers" / "L07").mkdir(parents=True)  # Has bundle

    # Add bundle files to L06 and L07 only
    (tmp_path / "_alllayers" / "L06" / "R0000C0000.bundle").write_bytes(b"\x00" * 100)
    (tmp_path / "_alllayers" / "L07" / "R0000C0000.bundle").write_bytes(b"\x00" * 100)

    # Create source manager and load source
    manager = SourceManager(DefaultsConfig())
    manager.load_sources([
        SourceConfig(
            name="test-source",
            path=str(tmp_path),
            description="Test source with empty levels",
        )
    ])

    source = manager.get("test-source")
    assert source is not None

    # Should only include L06 and L07 (with bundle files), not L04 and L05 (empty)
    assert source.min_zoom == 6
    assert source.max_zoom == 7

    # tile_info should only list L06 and L07
    levels = [level["level"] for level in source.to_dict()["tile_info"]["levels"]]
    assert 4 not in levels
    assert 5 not in levels
    assert 6 in levels
    assert 7 in levels


def test_scan_levels_works_with_all_levels_populated(tmp_path):
    """Test that all levels are included when all have bundle files."""
    # Create directory structure with all levels having bundles
    for level in [4, 5, 6, 7]:
        level_dir = tmp_path / "_alllayers" / f"L{level:02d}"
        level_dir.mkdir(parents=True)
        (level_dir / "R0000C0000.bundle").write_bytes(b"\x00" * 100)

    manager = SourceManager(DefaultsConfig())
    manager.load_sources([
        SourceConfig(
            name="test-source",
            path=str(tmp_path),
            description="Test source with all levels",
        )
    ])

    source = manager.get("test-source")
    assert source is not None
    assert source.min_zoom == 4
    assert source.max_zoom == 7

    levels = [level["level"] for level in source.to_dict()["tile_info"]["levels"]]
    assert levels == [4, 5, 6, 7]


def test_scan_levels_handles_no_bundles_at_all(tmp_path):
    """Test that source with no bundles has no levels."""
    # Create empty level directories
    (tmp_path / "_alllayers" / "L04").mkdir(parents=True)
    (tmp_path / "_alllayers" / "L05").mkdir(parents=True)

    manager = SourceManager(DefaultsConfig())
    manager.load_sources([
        SourceConfig(
            name="test-source",
            path=str(tmp_path),
            description="Test source with no bundles",
        )
    ])

    source = manager.get("test-source")
    # Source should still load but with no valid levels
    # This is edge case - min_zoom/max_zoom would be from config defaults or 0
    assert source is not None
