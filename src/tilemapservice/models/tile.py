"""Tile request, response, and source location models."""
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field


class TileRequest(BaseModel):
    """瓦片请求参数模型"""
    source_name: str = Field(..., description="数据源名称", examples=["world", "china"])
    z: int = Field(..., description="缩放级别", ge=0, le=22, examples=[5, 10, 15])
    x: int = Field(..., description="瓦片列号（X坐标）", ge=0, examples=[13, 27, 54])
    y: int = Field(..., description="瓦片行号（Y坐标）", ge=0, examples=[6, 12, 24])
    srs: str = Field(default="EPSG:3857", description="空间参考系统", examples=["EPSG:3857", "EPSG:4326"])
    matrix: str = Field(default="webmercator", description="瓦片矩阵标识符", examples=["webmercator", "tms", "source"])
    output_format: str = Field(default="auto", description="输出图片格式", examples=["auto", "png", "jpeg"])
    service_type: str = Field(default="xyz", description="服务类型", examples=["xyz", "tms", "wmts"])


@dataclass
class TileLocation:
    request_x: int
    request_y: int
    source_level: int
    source_tile_x: int
    source_tile_y: int
    local_row: int
    local_col: int
    bundle_path: Path


@dataclass
class TileResponse:
    data: bytes
    content_type: str
    source_name: str
    z: int
    x: int
    y: int
    source_level: int
    source_tile_x: int
    source_tile_y: int

