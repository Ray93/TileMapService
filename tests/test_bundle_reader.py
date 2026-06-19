import struct

import pytest

from tilemapservice.readers.bundle_reader import BundleReader, TileIndexCalculator
from tilemapservice.utils.exceptions import BundleFormatError


def test_v2_read_first_tile(v2_bundle):
    with BundleReader(v2_bundle) as reader:
        assert not reader.is_v1
        assert reader.get_tile(0, 0).startswith(b"\xff\xd8")
        assert reader.get_tile(0, 1) is None


def test_v1_read_first_tile(v1_bundle):
    with BundleReader(v1_bundle) as reader:
        assert reader.is_v1
        assert reader.get_tile(0, 0).startswith(b"\xff\xd8")


def test_v1_index_uses_column_major_local_tile_order(tmp_path):
    bundle = tmp_path / "R0000C0000.bundle"
    bundlx = tmp_path / "R0000C0000.bundlx"
    tile = b"\x89PNGcol-major"
    bundle.write_bytes(b"\x00" * 64 + len(tile).to_bytes(4, "little") + tile)
    entries = bytearray(b"\x00" * 16)
    for index in range(128 * 128):
        offset = 64 if index == 1 else 0
        entries.extend(offset.to_bytes(5, "little"))
    bundlx.write_bytes(bytes(entries))

    with BundleReader(bundle) as reader:
        assert reader.is_v1
        assert reader.get_tile(1, 0) == tile
        assert reader.get_tile(0, 1) is None


def test_v2_invalid_data_offset_raises(tmp_path):
    path = tmp_path / "bad.bundle"
    header = bytearray(64)
    struct.pack_into("<I", header, 8, 1)
    path.write_bytes(bytes(header))
    with pytest.raises(BundleFormatError):
        BundleReader(path)


def test_bundle_path_tries_lower_and_uppercase(tmp_path):
    level_dir = tmp_path / "L16"
    level_dir.mkdir()
    upper = level_dir / "R0080C0100.bundle"
    upper.write_bytes(b"x")
    path, row, col = TileIndexCalculator.find_bundle_path(level_dir, x=256, y=128)
    assert path == upper
    assert row == 0
    assert col == 0
