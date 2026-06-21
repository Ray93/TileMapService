from fastapi.testclient import TestClient

from main import create_app
from tilemapservice.models.config import AppConfig, SourceConfig
from tilemapservice.models.tile import TileResponse


class DummyTileService:
    """Minimal tile service that always returns 404 (TileNotFoundError)."""

    def get_tile(self, request):
        from tilemapservice.utils.exceptions import TileNotFoundError

        raise TileNotFoundError("Tile not found")


def test_health_includes_cache_enabled():
    app = create_app(AppConfig())
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["cache_enabled"] is True


def test_stats_endpoint_includes_source_stats():
    """Per-source stats appear in /api/stats for known sources."""
    config = AppConfig(sources=[SourceConfig(name="test-source", path="./data")])
    app = create_app(config)
    app.state.tile_service = DummyTileService()
    client = TestClient(app, raise_server_exceptions=False)
    # Trigger a 404 for a known source
    client.get("/tiles/test-source/0/0/0")
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "test-source" in data["sources"]
    assert data["sources"]["test-source"]["requests"] >= 1


def test_unknown_source_does_not_create_unbounded_keys():
    """Unknown sources must not each create a unique key in source_stats.

    They should be grouped under '_unknown' to prevent memory exhaustion from
    attacker-controlled source names. This guards against the point #3 bug:
    unbounded dictionary growth from arbitrary source/layer names.
    """
    app = create_app(AppConfig())
    app.state.tile_service = DummyTileService()
    client = TestClient(app, raise_server_exceptions=False)
    # Request 100 different non-existent sources
    for i in range(100):
        client.get(f"/tiles/fake-source-{i}/0/0/0")
    response = client.get("/api/stats")
    data = response.json()
    # All unknown sources should be grouped under '_unknown', not 100 keys
    assert len(data["sources"]) == 1
    assert "_unknown" in data["sources"]
    assert data["sources"]["_unknown"]["requests"] == 100
    # Confirm no individual fake-source-N keys
    for i in range(100):
        assert f"fake-source-{i}" not in data["sources"]

