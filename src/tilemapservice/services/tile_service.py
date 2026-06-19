"""Tile service orchestration."""
from tilemapservice.models.tile import TileRequest, TileResponse
from tilemapservice.readers.bundle_reader import BundleReader
from tilemapservice.services.cache import TileCache
from tilemapservice.services.image_formatter import ImageFormatter
from tilemapservice.services.tile_locator import TileLocator
from tilemapservice.utils.exceptions import SourceNotFoundError, TileNotFoundError


class TileService:
    """Coordinates lookup, raw cache, bundle reads, and output formatting."""

    def __init__(self, source_manager, cache: TileCache, stats, bundle_pool=None):
        self.sources = source_manager
        self.cache = cache
        self.stats = stats
        self.bundle_pool = bundle_pool
        self.locator = TileLocator()
        self.formatter = ImageFormatter()

    def get_tile(self, request: TileRequest) -> TileResponse:
        source = self.sources.get(request.source_name)
        if source is None:
            raise SourceNotFoundError("数据源不存在", {"source": request.source_name})

        location = self.locator.locate(request, source)
        cache_key = f"{request.source_name}:{location.source_level}:{location.source_tile_x}:{location.source_tile_y}:raw"

        tile_data = self.cache.get(cache_key)
        if tile_data is None:
            self.stats.record_cache(hit=False, source=request.source_name)
            if not location.bundle_path.exists():
                raise TileNotFoundError("Bundle 文件不存在", {"bundle_path": str(location.bundle_path)})
            if self.bundle_pool:
                reader, reader_lock = self.bundle_pool.get(location.bundle_path)
                with reader_lock:  # Ensure thread-safe file operations
                    tile_data = reader.get_tile(location.local_row, location.local_col)
            else:
                with BundleReader(location.bundle_path) as reader:
                    tile_data = reader.get_tile(location.local_row, location.local_col)
            if tile_data is None:
                raise TileNotFoundError(
                    "瓦片不存在",
                    {
                        "bundle_path": str(location.bundle_path),
                        "local_row": location.local_row,
                        "local_col": location.local_col,
                    },
                )
            self.cache.set(cache_key, tile_data)
        else:
            self.stats.record_cache(hit=True, source=request.source_name)

        data, content_type = self.formatter.format(tile_data, request.output_format)
        return TileResponse(
            data=data,
            content_type=content_type,
            source_name=request.source_name,
            z=request.z,
            x=request.x,
            y=request.y,
            source_level=location.source_level,
            source_tile_x=location.source_tile_x,
            source_tile_y=location.source_tile_y,
        )

