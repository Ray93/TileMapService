from tilemapservice.models.config import AppConfig, SourceConfig
from main import load_config, parse_args


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


# --- Point #2: env-var override coverage & TILEMAPSERVICE_CONFIG path ---


def test_tilemapservice_config_env_sets_config_path(monkeypatch, tmp_path):
    """TILEMAPSERVICE_CONFIG selects the config file when --config is absent."""
    custom = tmp_path / "custom.yaml"
    custom.write_text("server:\n  port: 9999\n", encoding="utf-8")
    monkeypatch.setenv("TILEMAPSERVICE_CONFIG", str(custom))
    args = parse_args([])
    assert args.config == str(custom)


def test_cli_config_flag_overrides_config_env(monkeypatch, tmp_path):
    """Explicit --config wins over TILEMAPSERVICE_CONFIG."""
    env_cfg = tmp_path / "env.yaml"
    env_cfg.write_text("server:\n  port: 1111\n", encoding="utf-8")
    cli_cfg = tmp_path / "cli.yaml"
    cli_cfg.write_text("server:\n  port: 2222\n", encoding="utf-8")
    monkeypatch.setenv("TILEMAPSERVICE_CONFIG", str(env_cfg))
    args = parse_args(["--config", str(cli_cfg)])
    assert args.config == str(cli_cfg)


def test_env_overrides_bundle_pool_max_size(monkeypatch, tmp_path):
    """Multi-segment section (bundle_pool) must be overridable."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("bundle_pool:\n  max_size: 50\n", encoding="utf-8")
    monkeypatch.setenv("TILEMAPSERVICE_BUNDLE_POOL_MAX_SIZE", "200")
    assert load_config(str(config_path)).bundle_pool.max_size == 200


def test_env_overrides_defaults_tile_size(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("TILEMAPSERVICE_DEFAULTS_TILE_SIZE", "512")
    assert load_config(str(config_path)).defaults.tile_size == 512


def test_env_overrides_nested_spatial_ref_wkid(monkeypatch, tmp_path):
    """Nested fields like defaults.spatial_ref.wkid must be overridable."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("TILEMAPSERVICE_DEFAULTS_SPATIAL_REF_WKID", "4326")
    assert load_config(str(config_path)).defaults.spatial_ref.wkid == 4326


def test_env_overrides_float_field(monkeypatch, tmp_path):
    """Float fields must be parsed as float, not left as string."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("TILEMAPSERVICE_DEFAULTS_TILE_ORIGIN_X", "-180.0")
    value = load_config(str(config_path)).defaults.tile_origin.x
    assert value == -180.0
    assert isinstance(value, float)


def test_env_overrides_multiword_field_name(monkeypatch, tmp_path):
    """Underscore-bearing field names (graceful_shutdown_timeout) must match whole."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("TILEMAPSERVICE_SERVER_GRACEFUL_SHUTDOWN_TIMEOUT", "30")
    assert load_config(str(config_path)).server.graceful_shutdown_timeout == 30


def test_env_does_not_override_sources(monkeypatch, tmp_path):
    """TILEMAPSERVICE_SOURCES is explicitly not supported; config file value wins."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("sources:\n  - name: orig\n    path: ./data\n", encoding="utf-8")
    monkeypatch.setenv("TILEMAPSERVICE_SOURCES", "ignored")
    config = load_config(str(config_path))
    assert len(config.sources) == 1
    assert isinstance(config.sources[0], SourceConfig)
    assert config.sources[0].name == "orig"
