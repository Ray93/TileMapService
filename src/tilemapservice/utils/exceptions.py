"""TileMapService internal exception types."""
from dataclasses import dataclass
from typing import Any


@dataclass
class TileServiceError(Exception):
    """Base exception carrying a public message and structured context."""

    message: str
    context: dict[str, Any] | None = None


class InvalidTileRequestError(TileServiceError):
    """Request parameters are invalid."""


class SourceNotFoundError(TileServiceError):
    """Requested source does not exist."""


class TileNotFoundError(TileServiceError):
    """Requested tile does not exist."""


class BundleFormatError(TileServiceError):
    """Bundle or bundlx structure is invalid."""


class TileReadError(TileServiceError):
    """Tile bytes could not be read."""


class ImageFormatError(TileServiceError):
    """Image bytes could not be converted."""

