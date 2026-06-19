"""Tile image format detection and conversion."""
from io import BytesIO

from PIL import Image

from tilemapservice.utils.exceptions import ImageFormatError, InvalidTileRequestError


class ImageFormatter:
    """Convert raw tile bytes to requested output format."""

    def format(self, tile_data: bytes, output_format: str) -> tuple[bytes, str]:
        fmt = output_format.lower()
        if fmt not in ("auto", "png", "jpg", "jpeg"):
            raise InvalidTileRequestError("非法输出格式", {"format": output_format})

        if fmt == "auto":
            return tile_data, self.detect_content_type(tile_data)

        try:
            if fmt in ("jpg", "jpeg"):
                if tile_data[:2] == b"\xff\xd8":
                    return tile_data, "image/jpeg"
                img = Image.open(BytesIO(tile_data)).convert("RGB")
                output = BytesIO()
                img.save(output, format="JPEG", quality=85)
                return output.getvalue(), "image/jpeg"

            if fmt == "png":
                if tile_data[:4] == b"\x89PNG":
                    return tile_data, "image/png"
                img = Image.open(BytesIO(tile_data))
                output = BytesIO()
                img.save(output, format="PNG")
                return output.getvalue(), "image/png"
        except Exception as exc:
            raise ImageFormatError("瓦片图像格式转换失败", {"format": output_format}) from exc

        return tile_data, self.detect_content_type(tile_data)

    def detect_content_type(self, data: bytes) -> str:
        if data[:2] == b"\xff\xd8":
            return "image/jpeg"
        if data[:4] == b"\x89PNG":
            return "image/png"
        return "application/octet-stream"

