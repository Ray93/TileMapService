"""Data source model."""
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from tilemapservice.utils.coordinates import TileMatrixSet


class DataSource(BaseModel):
    """Tile data source."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "name": "world",
                "data_path": "/data/tiles/world",
                "description": "世界地图瓦片数据",
                "spatial_ref_wkid": 3857,
                "tile_origin": [-20037508.342787, 20037508.342787],
                "tile_size": 256,
                "bounds": [-180.0, -85.05112878, 180.0, 85.05112878],
                "levels": [
                    {"level": 0, "resolution": 156543.033928},
                    {"level": 1, "resolution": 78271.516964}
                ],
                "min_zoom": 0,
                "max_zoom": 18,
                "is_v1": False
            }
        }
    )

    name: str = Field(..., description="数据源唯一标识名称", examples=["world", "china", "satellite"])
    data_path: Path = Field(..., description="瓦片数据存储路径")
    description: str = Field(default="", description="数据源描述信息")
    spatial_ref_wkid: int = Field(default=3857, description="空间参考系统的WKID", examples=[3857, 4326, 4490])
    tile_origin: tuple[float, float] = Field(
        default=(-20037508.342787, 20037508.342787),
        description="瓦片原点坐标(X, Y)"
    )
    tile_size: int = Field(default=256, description="瓦片尺寸（像素）", examples=[256, 512])
    bounds: tuple[float, float, float, float] = Field(
        default=(-180.0, -90.0, 180.0, 90.0),
        description="数据边界范围(minX, minY, maxX, maxY)"
    )
    levels: list[dict] = Field(default_factory=list, description="瓦片层级定义列表")
    min_zoom: int = Field(default=0, description="最小缩放级别", ge=0)
    max_zoom: int = Field(default=18, description="最大缩放级别", le=22)
    is_v1: Optional[bool] = Field(default=None, description="是否为V1格式Bundle文件")
    tile_matrix_set: Optional[TileMatrixSet] = Field(default=None, description="瓦片矩阵集定义")

    @property
    def srs(self) -> str:
        return f"EPSG:{self.spatial_ref_wkid}"

    def get_epsg_code(self) -> int:
        """Extract EPSG code from SRS string."""
        if not self.srs:
            return 3857
        import re
        match = re.search(r"EPSG:(\d+)", self.srs, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 3857

    def get_level_dir(self, z: int) -> Path:
        alllayers = self.data_path / "_alllayers" / f"L{z:02d}"
        if alllayers.exists():
            return alllayers
        direct = self.data_path / f"L{z:02d}"
        if direct.exists():
            return direct
        raise FileNotFoundError(f"层级目录不存在: L{z:02d}")

    def to_dict(self) -> dict:
        """Serialize DataSource to dict for API responses."""
        crs_def = self._build_crs_definition()
        resolutions = []
        if self.tile_matrix_set:
            resolutions = [
                self.tile_matrix_set.tile_resolution(z)
                for z in range(self.min_zoom, self.max_zoom + 1)
            ]

        return {
            "name": self.name,
            "description": self.description,
            "srs": self.srs,
            "bounds": list(self.bounds),
            "min_zoom": self.min_zoom,
            "max_zoom": self.max_zoom,
            "tile_info": {
                "tile_size": self.tile_size,
                "tile_origin": {"x": self.tile_origin[0], "y": self.tile_origin[1]},
                "levels": self.levels,
                "matrix": self.tile_matrix_set.name if self.tile_matrix_set else "source",
            },
            "tile_matrix": {
                "crs": self.srs,
                "is_geographic": crs_def["is_geographic"],
                "proj4": crs_def["proj4"],
                "wkt": crs_def["wkt"],
                "origin": {"x": self.tile_origin[0], "y": self.tile_origin[1]},
                "tile_size": self.tile_size,
                "resolutions": resolutions,
                "min_zoom": self.min_zoom,
                "max_zoom": self.max_zoom,
            },
            "tile_url_template": f"/tiles/{self.name}/{{z}}/{{x}}/{{y}}",
        }

    def _build_crs_definition(self) -> dict:
        """Generate CRS definition (proj4, WKT, is_geographic) from pyproj.

        Returns dict with keys: is_geographic, proj4, wkt.
        All values are None if CRS parsing fails (invalid WKID).
        """
        from pyproj import CRS
        try:
            crs = CRS.from_user_input(self.srs)
            return {
                "is_geographic": crs.is_geographic,
                "proj4": crs.to_proj4(),
                "wkt": crs.to_wkt(),
            }
        except Exception:
            return {"is_geographic": None, "proj4": None, "wkt": None}

