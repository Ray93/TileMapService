"""Data source manager."""
from pathlib import Path
from typing import Optional

from tilemapservice.models.config import DefaultsConfig, SourceConfig
from tilemapservice.models.source import DataSource
from tilemapservice.readers.bundle_reader import TileIndexCalculator
from tilemapservice.readers.cdi_parser import CdiParser
from tilemapservice.readers.conf_parser import ConfParser
from tilemapservice.utils.coordinates import TileMatrixSet


class SourceManager:
    """Loads and stores configured sources."""

    def __init__(self, defaults: DefaultsConfig):
        self.defaults = defaults
        self._sources: dict[str, DataSource] = {}

    def load_sources(self, source_configs: list[SourceConfig]) -> None:
        for config in source_configs:
            self._sources[config.name] = self._load_source(config)

    def _load_source(self, config: SourceConfig) -> DataSource:
        data_path = Path(config.path)
        conf_path = data_path / "Conf.xml"
        if conf_path.exists():
            conf = ConfParser(conf_path)
            sr = conf.get_spatial_reference()
            tile_origin = conf.get_tile_origin()
            tile_info = conf.get_tile_info()
            levels = conf.get_levels()
            wkid = sr["wkid"]
            origin_x, origin_y = tile_origin["x"], tile_origin["y"]
            tile_size = tile_info["tile_cols"]
        else:
            wkid = config.spatial_ref.wkid if config.spatial_ref else self.defaults.spatial_ref.wkid
            origin = config.tile_origin if config.tile_origin else self.defaults.tile_origin
            origin_x, origin_y = origin.x, origin.y
            tile_size = self.defaults.tile_size
            levels = []

        scanned_levels = self._scan_levels(data_path)
        if not levels:
            default_resolution = 40075016.68557849 / 256 if wkid == 3857 else 180.0 / 256
            levels = [{"level": level, "scale": 0.0, "resolution": default_resolution / (1 << level)} for level in scanned_levels or [0]]
        resolutions = {level["level"]: level["resolution"] for level in levels if level.get("resolution", 0) > 0}
        min_zoom = min(scanned_levels) if scanned_levels else min(resolutions)
        max_zoom = max(scanned_levels) if scanned_levels else max(resolutions)
        tile_matrix_set = TileMatrixSet(
            "source",
            f"EPSG:{wkid}",
            origin_x,
            origin_y,
            tile_size,
            tile_size,
            resolutions,
        )

        cdi_path = data_path / "conf.cdi"
        if cdi_path.exists():
            bounds = CdiParser(cdi_path).get_bounds()
        elif config.bounds:
            bounds = tuple(config.bounds)
        elif self.defaults.infer_bounds:
            bounds = self._infer_bounds(data_path, tile_matrix_set, sorted(scanned_levels, reverse=True))
            # If inference failed, use default bounds
            if bounds is None:
                if wkid == 3857:
                    bounds = (-20037508.342787, -20037508.342787, 20037508.342787, 20037508.342787)
                elif wkid == 4326:
                    bounds = (-180.0, -90.0, 180.0, 90.0)
                else:
                    bounds = (-180.0, -90.0, 180.0, 90.0)
        else:
            # Use default bounds based on WKID
            if wkid == 3857:
                bounds = (-20037508.342787, -20037508.342787, 20037508.342787, 20037508.342787)
            elif wkid == 4326:
                bounds = (-180.0, -90.0, 180.0, 90.0)
            else:
                bounds = (-180.0, -90.0, 180.0, 90.0)  # Default to geographic

        return DataSource(
            name=config.name,
            data_path=data_path,
            description=config.description or "",
            spatial_ref_wkid=wkid,
            tile_origin=(origin_x, origin_y),
            tile_size=tile_size,
            bounds=bounds,
            levels=levels,
            min_zoom=min_zoom,
            max_zoom=max_zoom,
            tile_matrix_set=tile_matrix_set,
        )

    def _scan_levels(self, data_path: Path) -> list[int]:
        levels = set()
        for pattern in ("_alllayers/L*", "L*"):
            for path in data_path.glob(pattern):
                if path.is_dir() and path.name.startswith("L"):
                    suffix = path.name[1:]
                    if suffix.isdigit():
                        # Only include level if it contains at least one bundle file
                        if any(path.glob("*.bundle")):
                            levels.add(int(suffix))
        return sorted(levels)

    def _infer_bounds(
        self,
        data_path: Path,
        tile_matrix_set: TileMatrixSet,
        levels: list[int],
    ) -> Optional[tuple[float, float, float, float]]:
        inferred_bounds = []
        for level in levels:
            level_dir = self._level_dir(data_path, level)
            if level_dir is None:
                continue

            tile_ranges = []
            width, height = tile_matrix_set.matrix_size(level)
            for bundle_path in level_dir.glob("*.bundle"):
                try:
                    row, col = TileIndexCalculator.parse_bundle_name(bundle_path.name)
                except (ValueError, IndexError):
                    continue
                if row >= height or col >= width:
                    continue
                tile_ranges.append(
                    (
                        col,
                        row,
                        min(col + TileIndexCalculator.BUNDLE_SIZE - 1, width - 1),
                        min(row + TileIndexCalculator.BUNDLE_SIZE - 1, height - 1),
                    )
                )

            if not tile_ranges:
                continue

            min_tile_x = min(item[0] for item in tile_ranges)
            min_tile_y = min(item[1] for item in tile_ranges)
            max_tile_x = max(item[2] for item in tile_ranges)
            max_tile_y = max(item[3] for item in tile_ranges)

            bounds = [
                tile_matrix_set.tile_bounds_to_crs(min_tile_x, min_tile_y, level),
                tile_matrix_set.tile_bounds_to_crs(max_tile_x, max_tile_y, level),
            ]
            xs = [bounds[0][0], bounds[0][2], bounds[1][0], bounds[1][2]]
            ys = [bounds[0][1], bounds[0][3], bounds[1][1], bounds[1][3]]
            inferred_bounds.append((min(xs), min(ys), max(xs), max(ys)))

        if not inferred_bounds:
            return None

        return (
            min(bounds[0] for bounds in inferred_bounds),
            min(bounds[1] for bounds in inferred_bounds),
            max(bounds[2] for bounds in inferred_bounds),
            max(bounds[3] for bounds in inferred_bounds),
        )

    def _level_dir(self, data_path: Path, level: int) -> Optional[Path]:
        for candidate in (data_path / "_alllayers" / f"L{level:02d}", data_path / f"L{level:02d}"):
            if candidate.exists():
                return candidate
        return None

    def get(self, name: str) -> Optional[DataSource]:
        return self._sources.get(name)

    def list_all(self) -> list[DataSource]:
        return list(self._sources.values())

    def count(self) -> int:
        return len(self._sources)
