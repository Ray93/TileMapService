"""WMTS service logic."""
from tilemapservice.models.source import DataSource
from tilemapservice.models.tile import TileResponse
from tilemapservice.models.wmts import WmtsTileRequest
from tilemapservice.services.tile_service import TileService
from tilemapservice.services.source_manager import SourceManager
from tilemapservice.utils.exceptions import InvalidTileRequestError, SourceNotFoundError


class WmtsService:
    """Handles WMTS tile requests."""

    def __init__(self, tile_service: TileService, source_manager: SourceManager):
        self.tile_service = tile_service
        self.source_manager = source_manager

    def parse_tilematrixset(self, tilematrixset: str) -> tuple[str, str]:
        """Parse TileMatrixSet identifier to (matrix_type, crs)."""
        if tilematrixset == "WebMercator":
            return ("webmercator", "EPSG:3857")
        if tilematrixset == "Geographic":
            return ("geographic", "EPSG:4326")
        if tilematrixset == "WebMercator-native":
            return ("source", "EPSG:3857")
        if tilematrixset == "Geographic-native":
            return ("source", "EPSG:4326")
        if tilematrixset.endswith("-native"):
            epsg_part = tilematrixset.replace("-native", "")
            return ("source", epsg_part)
        if tilematrixset.startswith("EPSG:"):
            return ("source", tilematrixset)
        return ("webmercator", "EPSG:3857")

    def validate_crs_compatibility(self, request: WmtsTileRequest, source: DataSource) -> None:
        """Validate CRS compatibility for native TileMatrixSet requests."""
        _, request_crs = self.parse_tilematrixset(request.tilematrixset)
        source_crs = source.srs.upper() if source.srs else "EPSG:3857"

        request_crs = request_crs.upper()
        if not source_crs.startswith("EPSG:"):
            source_crs = f"EPSG:{source_crs}"

        if request.tilematrixset.endswith("-native") or request.tilematrixset.startswith("EPSG:"):
            if request_crs != source_crs:
                raise InvalidTileRequestError(
                    f"native TileMatrixSet requires CRS match: request={request_crs}, source={source_crs}",
                    {"layer": request.layer, "tilematrixset": request.tilematrixset},
                )

    def get_tile(self, request: WmtsTileRequest) -> TileResponse:
        """Get tile for WMTS request."""
        source = self.source_manager.get(request.layer)
        if source is None:
            raise SourceNotFoundError(
                f"WMTS layer '{request.layer}' not found",
                {"layer": request.layer},
            )

        self.validate_crs_compatibility(request, source)
        tile_request = request.to_tile_request()
        return self.tile_service.get_tile(tile_request)