from tilemapservice.models.config import AppConfig, SourceConfig
from main import load_config


def test_default_config_instantiates():
    config = AppConfig()
    assert config.server.port == 8000
    assert config.cache.enabled is True
    assert config.defaults.spatial_ref.wkid == 3857


def test_source_config_minimal():
    source = SourceConfig(name="test", path="./data")
    assert source.name == "test"
    assert source.path == "./data"


def test_env_bool_false_is_parsed_as_false(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("cache:\n  enabled: true\n", encoding="utf-8")
    monkeypatch.setenv("TILEMAPSERVICE_CACHE_ENABLED", "false")
    assert load_config(str(config_path)).cache.enabled is False
