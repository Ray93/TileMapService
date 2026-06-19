from fastapi.testclient import TestClient

from main import create_app
from tilemapservice.models.config import AppConfig


def test_health_includes_cache_enabled():
    app = create_app(AppConfig())
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["cache_enabled"] is True

