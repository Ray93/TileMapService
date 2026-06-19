import pytest

from tilemapservice.services.image_formatter import ImageFormatter
from tilemapservice.utils.exceptions import InvalidTileRequestError


def test_auto_detects_jpeg():
    data, content_type = ImageFormatter().format(b"\xff\xd8abc\xff\xd9", "auto")
    assert data == b"\xff\xd8abc\xff\xd9"
    assert content_type == "image/jpeg"


def test_invalid_format_raises_400_error_type():
    with pytest.raises(InvalidTileRequestError):
        ImageFormatter().format(b"data", "gif")

