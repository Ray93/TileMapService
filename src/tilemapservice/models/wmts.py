"""WMTS request and response models."""
from dataclasses import dataclass

from tilemapservice.models.tile import TileRequest


@dataclass
class WmtsTileRequest:
    """WMTS GetTile request parameters."""

    layer: str
    style: str
    tilematrixset: str
    tilematrix: int
    tilerow: int
    tilecol: int
    format: str = "image/png"

    def to_tile_request(self) -> TileRequest:
        """Convert WMTS request to internal TileRequest format."""
        # Extract format extension (image/png -> png, image/jpeg -> jpeg)
        output_format = self.format.split("/")[-1] if "/" in self.format else self.format
        # Map WMTS tilematrixset to internal matrix name
        matrix_name = self._parse_tilematrixset_to_matrix()
        crs = self._parse_tilematrixset_to_crs()

        return TileRequest(
            source_name=self.layer,
            z=self.tilematrix,
            x=self.tilecol,
            y=self.tilerow,
            srs=crs,
            matrix=matrix_name,
            output_format=output_format,
            service_type="xyz",
        )

    def _parse_tilematrixset_to_matrix(self) -> str:
        """Parse TileMatrixSet identifier to internal matrix name."""
        if self.tilematrixset == "WebMercator":
            return "webmercator"
        if self.tilematrixset == "Geographic":
            return "geographic"
        if self.tilematrixset.endswith("-native"):
            return "source"
        if self.tilematrixset.startswith("EPSG:"):
            return "source"
        return "webmercator"

    def _parse_tilematrixset_to_crs(self) -> str:
        """Parse TileMatrixSet identifier to CRS code."""
        if self.tilematrixset == "WebMercator":
            return "EPSG:3857"
        if self.tilematrixset == "Geographic":
            return "EPSG:4326"
        if self.tilematrixset == "WebMercator-native":
            return "EPSG:3857"
        if self.tilematrixset == "Geographic-native":
            return "EPSG:4326"
        if self.tilematrixset.startswith("EPSG:"):
            base = self.tilematrixset.replace("-native", "")
            return base
        return "EPSG:3857"