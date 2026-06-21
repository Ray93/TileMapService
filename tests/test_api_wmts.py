"""Tests for WMTS API routes."""
import pytest
from fastapi.testclient import TestClient

from main import create_app
from tilemapservice.models.config import AppConfig
from tilemapservice.models.tile import TileResponse
from tilemapservice.models.source import DataSource


class OkTileService:
    """Mock tile service that returns successful responses."""

    def get_tile(self, request):
        return TileResponse(
            data=b"\x89PNG\r\n\x1a\nfake-png",
            content_type="image/png",
            source_name=request.source_name,
            z=request.z,
            x=request.x,
            y=request.y,
            source_level=request.z,
            source_tile_x=request.x,
            source_tile_y=request.y,
        )


class MockSourceManager:
    """Mock source manager that returns a test source."""

    def __init__(self):
        self._source = DataSource(
            name="test",
            data_path="/tmp/test",
            spatial_ref_wkid=3857,
        )

    def get(self, name: str):
        if name == "test":
            return self._source
        return None

    def load_sources(self, sources):
        pass


class TestWmtsRoot:
    """Tests for WMTS root endpoint."""

    def test_invalid_service_returns_error(self):
        """Invalid service parameter returns ServiceException."""
        app = create_app(AppConfig())
        client = TestClient(app)
        response = client.get("/wmts?service=WFS&request=GetCapabilities")
        assert response.status_code == 400
        assert b"ServiceException" in response.content
        assert b"InvalidParameterValue" in response.content

    def test_unknown_request_returns_error(self):
        """Unknown request type returns ServiceException."""
        app = create_app(AppConfig())
        client = TestClient(app)
        response = client.get("/wmts?service=WMTS&request=UnknownRequest")
        assert response.status_code == 400
        assert b"ServiceException" in response.content
        assert b"OperationNotSupported" in response.content


class TestGetCapabilities:
    """Tests for GetCapabilities endpoint."""

    def test_get_capabilities_not_initialized(self):
        """GetCapabilities returns error when capabilities not initialized."""
        app = create_app(AppConfig())
        client = TestClient(app)
        response = client.get("/wmts?service=WMTS&request=GetCapabilities")
        assert response.status_code == 400
        assert b"ServiceException" in response.content

    def test_get_capabilities_returns_xml(self):
        """GetCapabilities returns XML when capabilities are set."""
        app = create_app(AppConfig())
        app.state.wmts_capabilities = b"""<?xml version="1.0"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0">
</Capabilities>"""
        client = TestClient(app)
        response = client.get("/wmts?service=WMTS&request=GetCapabilities")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"
        assert b"Capabilities" in response.content

    def test_get_capabilities_accepts_uppercase_kvp_parameters(self):
        """WMTS KVP parameters are case-insensitive in common clients."""
        app = create_app(AppConfig())
        app.state.wmts_capabilities = b"""<?xml version="1.0"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0">
</Capabilities>"""
        client = TestClient(app)
        response = client.get("/wmts?SERVICE=wmts&REQUEST=getcapabilities")
        assert response.status_code == 200
        assert b"Capabilities" in response.content


class TestGetTileKvp:
    """Tests for KVP GetTile endpoint."""

    def test_missing_layer_returns_error(self):
        """Missing layer parameter returns ServiceException."""
        app = create_app(AppConfig())
        client = TestClient(app)
        response = client.get(
            "/wmts?service=WMTS&request=GetTile"
            "&tilematrixset=WebMercator&tilematrix=0&tilerow=0&tilecol=0"
        )
        assert response.status_code == 400
        assert b"ServiceException" in response.content
        assert b"MissingParameterValue" in response.content
        assert b"layer" in response.content

    def test_missing_tilematrixset_returns_error(self):
        """Missing tilematrixset parameter returns ServiceException."""
        app = create_app(AppConfig())
        client = TestClient(app)
        response = client.get(
            "/wmts?service=WMTS&request=GetTile"
            "&layer=test&tilematrix=0&tilerow=0&tilecol=0"
        )
        assert response.status_code == 400
        assert b"ServiceException" in response.content
        assert b"MissingParameterValue" in response.content

    def test_missing_tilematrix_returns_error(self):
        """Missing tilematrix parameter returns ServiceException."""
        app = create_app(AppConfig())
        client = TestClient(app)
        response = client.get(
            "/wmts?service=WMTS&request=GetTile"
            "&layer=test&tilematrixset=WebMercator&tilerow=0&tilecol=0"
        )
        assert response.status_code == 400
        assert b"ServiceException" in response.content
        assert b"MissingParameterValue" in response.content

    def test_missing_tilerow_returns_error(self):
        """Missing tilerow parameter returns ServiceException."""
        app = create_app(AppConfig())
        client = TestClient(app)
        response = client.get(
            "/wmts?service=WMTS&request=GetTile"
            "&layer=test&tilematrixset=WebMercator&tilematrix=0&tilecol=0"
        )
        assert response.status_code == 400
        assert b"ServiceException" in response.content

    def test_missing_tilecol_returns_error(self):
        """Missing tilecol parameter returns ServiceException."""
        app = create_app(AppConfig())
        client = TestClient(app)
        response = client.get(
            "/wmts?service=WMTS&request=GetTile"
            "&layer=test&tilematrixset=WebMercator&tilematrix=0&tilerow=0"
        )
        assert response.status_code == 400
        assert b"ServiceException" in response.content

    def test_invalid_layer_returns_error(self):
        """Invalid layer returns LayerNotDefined ServiceException."""
        app = create_app(AppConfig())
        # All params are present and syntactically valid, so the request
        # reaches _serve_wmts_tile, which reads app.state.tile_service /
        # source_manager. The mock source manager only knows "test", so
        # layer=nonexistent -> SourceNotFoundError -> LayerNotDefined.
        app.state.tile_service = OkTileService()
        app.state.source_manager = MockSourceManager()
        client = TestClient(app)
        response = client.get(
            "/wmts?service=WMTS&request=GetTile"
            "&layer=nonexistent&tilematrixset=WebMercator"
            "&tilematrix=0&tilerow=0&tilecol=0"
        )
        assert response.status_code == 400
        assert b"ServiceException" in response.content
        assert b"LayerNotDefined" in response.content

    def test_valid_request_returns_tile(self):
        """Valid KVP GetTile request returns tile."""
        app = create_app(AppConfig())
        app.state.tile_service = OkTileService()
        app.state.source_manager = MockSourceManager()
        client = TestClient(app)
        response = client.get(
            "/wmts?service=WMTS&request=GetTile"
            "&layer=test&tilematrixset=WebMercator"
            "&tilematrix=0&tilerow=0&tilecol=0"
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert b"PNG" in response.content

    def test_get_tile_accepts_uppercase_kvp_parameters(self):
        """Uppercase WMTS KVP parameters should reach tile service."""
        app = create_app(AppConfig())
        app.state.tile_service = OkTileService()
        app.state.source_manager = MockSourceManager()
        client = TestClient(app)
        response = client.get(
            "/wmts?SERVICE=WMTS&REQUEST=GetTile"
            "&LAYER=test&TILEMATRIXSET=WebMercator"
            "&TILEMATRIX=0&TILEROW=0&TILECOL=0"
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"


class TestGetTileRestful:
    """Tests for RESTful GetTile endpoint."""

    def test_restful_get_tile_returns_tile(self):
        """RESTful GetTile returns tile."""
        app = create_app(AppConfig())
        app.state.tile_service = OkTileService()
        app.state.source_manager = MockSourceManager()
        client = TestClient(app)
        response = client.get("/wmts/test/default/WebMercator/0/0/0")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_restful_get_tile_with_format_extension(self):
        """RESTful GetTile with format extension returns tile."""
        app = create_app(AppConfig())
        app.state.tile_service = OkTileService()
        app.state.source_manager = MockSourceManager()
        client = TestClient(app)
        response = client.get("/wmts/test/default/WebMercator/0/0/0.png")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_restful_get_tile_with_jpg_extension(self):
        """RESTful GetTile with jpg extension returns tile with jpeg format."""
        app = create_app(AppConfig())
        app.state.tile_service = OkTileService()
        app.state.source_manager = MockSourceManager()
        client = TestClient(app)
        response = client.get("/wmts/test/default/WebMercator/0/0/0.jpg")
        assert response.status_code == 200


class TestServiceExceptionFormat:
    """Tests for ServiceException XML format."""

    def test_service_exception_xml_format(self):
        """ServiceException has correct XML format."""
        app = create_app(AppConfig())
        client = TestClient(app)
        response = client.get("/wmts?service=WMTS&request=GetTile")
        assert response.status_code == 400
        assert response.headers["content-type"] == "application/xml"
        # Check XML structure
        assert b"<?xml" in response.content
        assert b"ServiceExceptionReport" in response.content
        assert b"ServiceException" in response.content

    def test_service_exception_escapes_special_chars(self):
        """ServiceException escapes XML special characters."""
        app = create_app(AppConfig())
        client = TestClient(app)
        # Use a request that will trigger an error with potential XML chars
        response = client.get("/wmts?service=WMTS&request=GetTile&layer=<test>")
        assert response.status_code == 400
        # The error message should have escaped special chars
        assert b"&lt;" in response.content or b"<test>" not in response.content


class TestNegativeTileCoords:
    """Negative tilematrix/tilerow/tilecol and out-of-range tilematrix must not
    raise 500; return 400 ServiceException (InvalidParameterValue).

    Same root cause as /tiles: uncaught pydantic ValidationError when
    TileRequest is built with negative/out-of-range coords.
    """

    @pytest.mark.parametrize(
        "url",
        [
            "/wmts/test/default/WebMercator/-1/0/0",   # negative tilematrix (z)
            "/wmts/test/default/WebMercator/0/-1/0",     # negative tilerow (y)
            "/wmts/test/default/WebMercator/0/0/-1",      # negative tilecol (x)
            "/wmts/test/default/WebMercator/23/0/0",      # tilematrix out of range
            "/wmts?service=WMTS&request=GetTile&layer=test&tilematrixset=WebMercator&tilematrix=-1&tilerow=0&tilecol=0",  # KVP
        ],
    )
    def test_negative_coords_return_400_not_500(self, url):
        app = create_app(AppConfig())
        app.state.tile_service = OkTileService()
        app.state.source_manager = MockSourceManager()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(url)
        assert response.status_code == 400, f"{url} returned {response.status_code}"
        assert b"ServiceException" in response.content
        assert b"InvalidParameterValue" in response.content

    def test_valid_coords_still_succeed(self):
        """Regression guard: valid WMTS coords must keep returning 200."""
        app = create_app(AppConfig())
        app.state.tile_service = OkTileService()
        app.state.source_manager = MockSourceManager()
        client = TestClient(app)
        response = client.get("/wmts/test/default/WebMercator/0/0/0")
        assert response.status_code == 200
