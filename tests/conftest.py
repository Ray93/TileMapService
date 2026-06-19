import struct
from pathlib import Path

import pytest


JPEG = b"\xff\xd8fake-jpeg\xff\xd9"
PNG = b"\x89PNG\r\n\x1a\nfake-png"


def make_v2_bundle(path: Path, tile_index: int = 0, payload: bytes = JPEG) -> Path:
    tile_count = 128 * 128
    data_offset = 64 + tile_count * 8
    data_start = data_offset + 4
    header = bytearray(64)
    struct.pack_into("<I", header, 8, data_offset)
    index = bytearray(tile_count * 8)
    struct.pack_into("<I", index, tile_index * 8, data_start)
    path.write_bytes(bytes(header) + bytes(index) + struct.pack("<I", len(payload)) + payload)
    return path


def make_v1_bundle(path: Path, tile_index: int = 0, payload: bytes = JPEG) -> Path:
    bundle = path
    bundlx = path.with_suffix(".bundlx")
    data_offset = 4
    bundle.write_bytes(b"\x00\x00\x00\x00" + struct.pack("<I", len(payload)) + payload)
    index = bytearray(16 + 128 * 128 * 5)
    index[16 + tile_index * 5 : 16 + tile_index * 5 + 5] = data_offset.to_bytes(5, "little")
    bundlx.write_bytes(index)
    return bundle


@pytest.fixture
def v2_bundle(tmp_path):
    return make_v2_bundle(tmp_path / "R0000C0000.bundle")


@pytest.fixture
def v1_bundle(tmp_path):
    return make_v1_bundle(tmp_path / "R0000C0000.bundle")
