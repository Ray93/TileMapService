"""Application configuration models."""
from typing import Optional

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    graceful_shutdown_timeout: int = 5
    service_url: str = ""  # Optional: override WMTS service URL in capabilities


class CacheConfig(BaseModel):
    enabled: bool = True
    max_size: int = 1000
    ttl: int = 3600
    num_shards: int = Field(default=16, ge=1, le=256, description="缓存分片数（减少锁竞争）")


class CorsConfig(BaseModel):
    enabled: bool = True
    allow_origins: list[str] = Field(default_factory=lambda: ["*"])
    allow_methods: list[str] = Field(default_factory=lambda: ["GET"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])


class SpatialRef(BaseModel):
    wkid: int = 3857
    wkt: Optional[str] = None


class TileOrigin(BaseModel):
    x: float = -20037508.342787
    y: float = 20037508.342787


class BundlePoolConfig(BaseModel):
    enabled: bool = Field(default=True, description="启用 Bundle 连接池")
    max_size: int = Field(default=50, ge=1, le=500, description="最多保持打开的 Bundle 数")


class DefaultsConfig(BaseModel):
    spatial_ref: SpatialRef = Field(default_factory=SpatialRef)
    tile_origin: TileOrigin = Field(default_factory=TileOrigin)
    tile_size: int = 256
    infer_bounds: bool = True


class SourceConfig(BaseModel):
    name: str
    path: str
    description: Optional[str] = None
    spatial_ref: Optional[SpatialRef] = None
    tile_origin: Optional[TileOrigin] = None
    bounds: Optional[list[float]] = None


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    bundle_pool: BundlePoolConfig = Field(default_factory=BundlePoolConfig)
    sources: list[SourceConfig] = Field(default_factory=list)
