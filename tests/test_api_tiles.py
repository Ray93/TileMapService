import pytest
from fastapi.testclient import TestClient

from main import create_app
from tilemapservice.models.config import AppConfig
from tilemapservice.models.tile import TileResponse
from tilemapservice.utils.exceptions import BundleFormatError, InvalidTileRequestError


class InvalidTileService:
    def get_tile(self, request):
        raise InvalidTileRequestError("非法输出格式", {"format": request.output_format})


class BundleBrokenTileService:
    def get_tile(self, request):
        raise BundleFormatError("Bundle 损坏", {"source": request.source_name})


class OkTileService:
    def get_tile(self, request):
        return TileResponse(
            data=b"\xff\xd8ok\xff\xd9",
            content_type="image/jpeg",
            source_name=request.source_name,
            z=request.z,
            x=request.x,
            y=request.y,
            source_level=request.z,
            source_tile_x=request.x,
            source_tile_y=request.y,
        )


def test_removed_ambiguous_epsg_short_route_returns_404():
    app = create_app(AppConfig())
    client = TestClient(app)
    assert client.get("/tiles/demo/4326/1/2/3").status_code == 404


def test_invalid_tile_request_maps_to_400():
    app = create_app(AppConfig())
    app.state.tile_service = InvalidTileService()
    client = TestClient(app)
    response = client.get("/tiles/demo/0/0/0?format=gif")
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "InvalidTileRequestError"


def test_bundle_format_error_maps_to_500():
    app = create_app(AppConfig())
    app.state.tile_service = BundleBrokenTileService()
    client = TestClient(app)
    response = client.get("/tiles/demo/0/0/0")
    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "BundleFormatError"


def test_tms_extension_route_and_crs_extension_route_are_supported():
    app = create_app(AppConfig())
    app.state.tile_service = OkTileService()
    client = TestClient(app)
    tms = client.get("/tiles/demo/tms/0/0/0.jpg")
    crs = client.get("/tiles/demo/crs/epsg:3857/0/0/0.jpg?matrix=webmercator")
    assert tms.status_code == 200
    assert crs.status_code == 200
    assert tms.headers["x-source-level"] == "0"


@pytest.mark.parametrize(
    "url",
    [
        "/tiles/demo/-1/0/0",       # negative z
        "/tiles/demo/0/-1/0",       # negative x
        "/tiles/demo/0/0/-1",      # negative y
        "/tiles/demo/23/0/0",       # z out of range (>22)
        "/tiles/demo/tms/-1/0/0",   # tms route, negative z
        "/tiles/demo/crs/epsg:3857/-1/0/0?matrix=webmercator",  # crs route, negative z
    ],
)
def test_invalid_tile_coords_return_400_not_500(url):
    """Negative z/x/y and out-of-range z must not raise 500; return 400 in unified format."""
    app = create_app(AppConfig())
    app.state.tile_service = OkTileService()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(url)
    assert response.status_code == 400, f"{url} returned {response.status_code}"
    detail = response.json()["detail"]
    assert detail["error"] == "ValidationError"
    assert "message" in detail


def test_valid_tile_coords_still_succeed():
    """Regression guard: valid coords must keep returning 200 after the fix."""
    app = create_app(AppConfig())
    app.state.tile_service = OkTileService()
    client = TestClient(app)
    response = client.get("/tiles/demo/0/0/0")
    assert response.status_code == 200
