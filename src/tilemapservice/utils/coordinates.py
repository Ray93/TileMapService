"""Tile Matrix Set and CRS coordinate utilities."""
from dataclasses import dataclass

import mercantile
from pyproj import CRS, Transformer


@dataclass
class TileMatrixSet:
    """Defines how /z/x/y maps to coordinates in a CRS."""

    name: str
    crs: str
    origin_x: float
    origin_y: float
    tile_width: int = 256
    tile_height: int = 256
    resolutions: dict[int, float] | None = None
    wmts_identifier: str = ""  # WMTS standard TileMatrixSet ID
    scale_denominators: dict[int, float] | None = None  # WMTS scale denominators per level

    def matrix_size(self, z: int) -> tuple[int, int]:
        if z < 0:
            raise ValueError("z must be non-negative")
        if self.name == "webmercator":
            return 1 << z, 1 << z
        if self.name == "geographic":
            return 1 << (z + 1), 1 << z
        if self.resolutions and z in self.resolutions:
            # Derive matrix size from the tile origin (which bounds the world)
            # and the per-level resolution. This works for any CRS whose origin
            # spans the full world (geographic degree-based like EPSG:4326/4490,
            # or projected like EPSG:3857), instead of hardcoding EPSG codes.
            res = self.resolutions[z]
            width = round((2 * abs(self.origin_x)) / (res * self.tile_width))
            height = round((2 * abs(self.origin_y)) / (res * self.tile_height))
            return max(width, 1), max(height, 1)
        raise ValueError("matrix_size must be configured for this Tile Matrix Set")

    def validate_tile(self, z: int, x: int, y: int) -> None:
        width, height = self.matrix_size(z)
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"tile out of range for matrix {self.name}: z={z}, x={x}, y={y}")

    def tile_resolution(self, z: int) -> float:
        if self.name == "webmercator":
            return 40075016.68557849 / ((1 << z) * self.tile_width)
        if self.name == "geographic":
            return 180.0 / ((1 << z) * self.tile_height)
        if self.resolutions and z in self.resolutions:
            return self.resolutions[z]
        raise ValueError(f"resolution missing for level {z}")

    def tms_to_xyz_y(self, y: int, z: int) -> int:
        _, height = self.matrix_size(z)
        return height - 1 - y

    def tile_bounds_to_crs(self, x: int, y: int, z: int) -> tuple[float, float, float, float]:
        self.validate_tile(z, x, y)
        if self.name == "webmercator":
            bounds = mercantile.xy_bounds(mercantile.Tile(x, y, z))
            return bounds.left, bounds.bottom, bounds.right, bounds.top

        res = self.tile_resolution(z)
        min_x = self.origin_x + x * self.tile_width * res
        max_x = self.origin_x + (x + 1) * self.tile_width * res
        max_y = self.origin_y - y * self.tile_height * res
        min_y = self.origin_y - (y + 1) * self.tile_height * res
        return min_x, min_y, max_x, max_y

    def tile_center_to_crs(self, x: int, y: int, z: int) -> tuple[float, float]:
        min_x, min_y, max_x, max_y = self.tile_bounds_to_crs(x, y, z)
        return (min_x + max_x) / 2, (min_y + max_y) / 2

    def crs_to_tile(self, coord_x: float, coord_y: float, z: int) -> tuple[int, int]:
        res = self.tile_resolution(z)
        return (
            int((coord_x - self.origin_x) / (self.tile_width * res)),
            int((self.origin_y - coord_y) / (self.tile_height * res)),
        )

    def select_closest_level(self, target_resolution: float) -> int:
        if not self.resolutions:
            raise ValueError("source resolutions required for level selection")
        return min(self.resolutions, key=lambda level: abs(self.resolutions[level] - target_resolution))


class CoordinateTransformer:
    """Transforms CRS coordinate values; tile numbering is handled by TileMatrixSet."""

    def __init__(self):
        self._transformers: dict[str, Transformer] = {}

    def normalize_epsg(self, epsg: str) -> str:
        epsg = epsg.strip()
        if not epsg.upper().startswith("EPSG:"):
            epsg = f"EPSG:{epsg}"
        return epsg.upper()

    def _get_transformer(self, from_epsg: str, to_epsg: str) -> Transformer:
        from_epsg = self.normalize_epsg(from_epsg)
        to_epsg = self.normalize_epsg(to_epsg)
        key = f"{from_epsg}:{to_epsg}"
        if key not in self._transformers:
            self._transformers[key] = Transformer.from_crs(
                CRS.from_user_input(from_epsg),
                CRS.from_user_input(to_epsg),
                always_xy=True,
            )
        return self._transformers[key]

    def transform_point(self, x: float, y: float, from_epsg: str, to_epsg: str) -> tuple[float, float]:
        from_epsg = self.normalize_epsg(from_epsg)
        to_epsg = self.normalize_epsg(to_epsg)
        if from_epsg == to_epsg:
            return x, y
        return self._get_transformer(from_epsg, to_epsg).transform(x, y)


# WMTS scale denominators for WebMercator (GoogleMapsCompatible)
WEBMERCATOR_SCALE_DENOMINATORS = {
    0: 559082264.0287178,
    1: 279541132.0143589,
    2: 139770566.0071794,
    3: 69885283.0035897,
    4: 34942641.5017949,
    5: 17471320.7508974,
    6: 8735660.3754487,
    7: 4367830.1877243,
    8: 2183915.0938622,
    9: 1091957.5469311,
    10: 545978.7734655,
    11: 272989.3867328,
    12: 136494.6933664,
    13: 68247.3466832,
    14: 34123.6733416,
    15: 17061.8366708,
    16: 8530.9183354,
    17: 4265.4591677,
    18: 2132.7295838,
}

# WMTS scale denominators for Geographic (WorldCRS84Quad)
GEOGRAPHIC_SCALE_DENOMINATORS = {
    0: 279541132.0143589,
    1: 139770566.0071794,
    2: 69885283.0035897,
    3: 34942641.5017949,
    4: 17471320.7508974,
    5: 8735660.3754487,
    6: 4367830.1877243,
    7: 2183915.0938622,
    8: 1091957.5469311,
    9: 545978.7734655,
    10: 272989.3867328,
    11: 136494.6933664,
    12: 68247.3466832,
    13: 34123.6733416,
    14: 17061.8366708,
    15: 8530.9183354,
    16: 4265.4591677,
    17: 2132.7295838,
    18: 1066.3647919,
}


def create_webmercator_matrix_set() -> TileMatrixSet:
    """Create standard WebMercator (GoogleMapsCompatible) TileMatrixSet for WMTS."""
    return TileMatrixSet(
        name="webmercator",
        crs="EPSG:3857",
        origin_x=-20037508.342787,
        origin_y=20037508.342787,
        tile_width=256,
        tile_height=256,
        wmts_identifier="WebMercator",
        scale_denominators=WEBMERCATOR_SCALE_DENOMINATORS.copy(),
    )


def create_geographic_matrix_set() -> TileMatrixSet:
    """Create standard Geographic (WorldCRS84Quad) TileMatrixSet for WMTS."""
    return TileMatrixSet(
        name="geographic",
        crs="EPSG:4326",
        origin_x=-180.0,
        origin_y=90.0,
        tile_width=256,
        tile_height=256,
        wmts_identifier="Geographic",
        scale_denominators=GEOGRAPHIC_SCALE_DENOMINATORS.copy(),
    )
