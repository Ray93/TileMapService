"""ESRI Compact Cache V1/V2 bundle reader."""
import struct
from pathlib import Path
from typing import Optional

from tilemapservice.utils.exceptions import BundleFormatError, TileReadError


class BundleReader:
    """Reads tiles from V1 (.bundle + .bundlx) and V2 (.bundle) compact caches."""

    BUNDLE_SIZE = 128
    TILE_COUNT = BUNDLE_SIZE * BUNDLE_SIZE
    V2_HEADER_SIZE = 64
    V2_DATA_OFFSET = 8
    V2_INDEX_ENTRY_SIZE = 8
    V1_HEADER_SIZE = 16
    V1_INDEX_ENTRY_SIZE = 5

    def __init__(self, bundle_path: str | Path):
        self.bundle_path = Path(bundle_path)
        self.bundlx_path = self.bundle_path.with_suffix(".bundlx")
        self.is_v1 = self.bundlx_path.exists()
        self.bundlx_file = None
        if not self.bundle_path.exists():
            raise FileNotFoundError(f"Bundle 文件不存在: {self.bundle_path}")
        self.file_size = self.bundle_path.stat().st_size
        self.bundle_file = open(self.bundle_path, "rb")
        try:
            if self.is_v1:
                self.bundlx_file = open(self.bundlx_path, "rb")
                self._load_v1_index()
            else:
                self._load_v2_index()
        except Exception:
            self.close()
            raise

    def _load_v2_index(self) -> None:
        self.bundle_file.seek(0)
        header = self.bundle_file.read(self.V2_HEADER_SIZE)
        if len(header) < self.V2_HEADER_SIZE:
            raise BundleFormatError("无效的 V2 Bundle 文件: 文件头过短", {"path": str(self.bundle_path)})
        min_index_size = self.TILE_COUNT * self.V2_INDEX_ENTRY_SIZE
        index_end = self.V2_HEADER_SIZE + min_index_size
        header_data_offset = struct.unpack_from("<I", header, self.V2_DATA_OFFSET)[0]
        self.data_offset = index_end
        if self.file_size < index_end:
            raise BundleFormatError(
                "无效的 V2 Bundle 文件: 索引区不足 16384 项",
                {"path": str(self.bundle_path), "data_offset": header_data_offset, "index_end": index_end},
            )

        self.bundle_file.seek(self.V2_HEADER_SIZE)
        index_data = self.bundle_file.read(min_index_size)
        self.v2_offsets: list[tuple[int, int]] = []
        for tile_index in range(self.TILE_COUNT):
            offset = struct.unpack_from("<I", index_data, tile_index * self.V2_INDEX_ENTRY_SIZE)[0]
            if offset in (0, 4):
                self.v2_offsets.append((0, 0))
                continue
            if offset < index_end or offset - 4 < 0 or offset > self.file_size:
                raise BundleFormatError(
                    "无效的 V2 Bundle 文件: tile offset 越界",
                    {"path": str(self.bundle_path), "offset": offset},
                )
            self.bundle_file.seek(offset - 4)
            length_bytes = self.bundle_file.read(4)
            if len(length_bytes) != 4:
                raise BundleFormatError(
                    "无效的 V2 Bundle 文件: tile length 缺失",
                    {"path": str(self.bundle_path), "offset": offset},
                )
            length = struct.unpack("<I", length_bytes)[0]
            if length == 0:
                self.v2_offsets.append((0, 0))
                continue
            if offset + length > self.file_size:
                raise BundleFormatError(
                    "无效的 V2 Bundle 文件: tile length 越界",
                    {"path": str(self.bundle_path), "offset": offset, "length": length},
                )
            self.v2_offsets.append((offset, length))

    def _load_v1_index(self) -> None:
        expected_size = self.V1_HEADER_SIZE + self.TILE_COUNT * self.V1_INDEX_ENTRY_SIZE
        if self.bundlx_path.stat().st_size < expected_size:
            raise BundleFormatError("无效的 V1 bundlx 文件: 索引区不足 16384 项", {"path": str(self.bundlx_path)})
        self.v1_offsets: list[int] = []
        self.bundlx_file.seek(self.V1_HEADER_SIZE)
        for _ in range(self.TILE_COUNT):
            entry = self.bundlx_file.read(self.V1_INDEX_ENTRY_SIZE)
            self.v1_offsets.append(int.from_bytes(entry, "little"))

    def get_tile(self, local_row: int, local_col: int) -> Optional[bytes]:
        if not (0 <= local_row < self.BUNDLE_SIZE and 0 <= local_col < self.BUNDLE_SIZE):
            return None
        try:
            if self.is_v1:
                tile_index = local_col * self.BUNDLE_SIZE + local_row
                return self._read_v1_tile(tile_index)
            tile_index = local_row * self.BUNDLE_SIZE + local_col
            return self._read_v2_tile(tile_index)
        except OSError as exc:
            raise TileReadError("读取 Bundle 瓦片失败", {"path": str(self.bundle_path), "tile_index": tile_index}) from exc

    def _read_v1_tile(self, tile_index: int) -> Optional[bytes]:
        offset = self.v1_offsets[tile_index]
        if offset == 0:
            return None
        if offset + 4 > self.file_size:
            raise BundleFormatError("无效的 V1 Bundle 文件: tile offset 越界", {"path": str(self.bundle_path), "offset": offset})
        self.bundle_file.seek(offset)
        length_bytes = self.bundle_file.read(4)
        if len(length_bytes) != 4:
            raise BundleFormatError("无效的 V1 Bundle 文件: tile length 缺失", {"path": str(self.bundle_path), "offset": offset})
        length = struct.unpack("<I", length_bytes)[0]
        if length == 0:
            return None
        if offset + 4 + length > self.file_size:
            raise BundleFormatError(
                "无效的 V1 Bundle 文件: tile length 越界",
                {"path": str(self.bundle_path), "offset": offset, "length": length},
            )
        return self.bundle_file.read(length)

    def _read_v2_tile(self, tile_index: int) -> Optional[bytes]:
        offset, length = self.v2_offsets[tile_index]
        if offset == 0 or length == 0:
            return None
        self.bundle_file.seek(offset)
        return self.bundle_file.read(length)

    def close(self) -> None:
        if hasattr(self, "bundle_file") and not self.bundle_file.closed:
            self.bundle_file.close()
        if self.bundlx_file and not self.bundlx_file.closed:
            self.bundlx_file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class TileIndexCalculator:
    """Tile coordinate to bundle file helper."""

    BUNDLE_SIZE = 128

    @staticmethod
    def bundle_name(row: int, col: int, uppercase: bool = False) -> str:
        row_text = f"{row:04X}" if uppercase else f"{row:04x}"
        col_text = f"{col:04X}" if uppercase else f"{col:04x}"
        return f"R{row_text}C{col_text}.bundle"

    @staticmethod
    def find_bundle_path(level_dir: Path, x: int, y: int) -> tuple[Path, int, int]:
        bundle_row = (y // TileIndexCalculator.BUNDLE_SIZE) * TileIndexCalculator.BUNDLE_SIZE
        bundle_col = (x // TileIndexCalculator.BUNDLE_SIZE) * TileIndexCalculator.BUNDLE_SIZE
        local_row = y % TileIndexCalculator.BUNDLE_SIZE
        local_col = x % TileIndexCalculator.BUNDLE_SIZE
        candidates = [
            level_dir / TileIndexCalculator.bundle_name(bundle_row, bundle_col, uppercase=False),
            level_dir / TileIndexCalculator.bundle_name(bundle_row, bundle_col, uppercase=True),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate, local_row, local_col
        return candidates[0], local_row, local_col

    @staticmethod
    def xyz_to_bundle_path(level_dir: Path, x: int, y: int) -> tuple[Path, int, int]:
        return TileIndexCalculator.find_bundle_path(level_dir, x, y)

    @staticmethod
    def parse_bundle_name(filename: str) -> tuple[int, int]:
        name = Path(filename).stem
        row_part, col_part = name.split("C")
        return int(row_part[1:], 16), int(col_part, 16)
