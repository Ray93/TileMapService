import sys
import types

from main import apply_cli_overrides, main, parse_args
from tilemapservice.models.config import AppConfig


def test_parse_args_and_apply_cli_overrides():
    args = parse_args([
        "--host",
        "127.0.0.1",
        "--port",
        "9000",
        "--cache-size",
        "42",
        "--debug",
        "--cors",
        "--graceful-shutdown-timeout",
        "3",
    ])
    config = apply_cli_overrides(AppConfig(), args)
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 9000
    assert config.server.debug is True
    assert config.server.graceful_shutdown_timeout == 3
    assert config.cache.max_size == 42
    assert config.cors.enabled is True


def test_main_passes_finite_graceful_shutdown_timeout_to_uvicorn(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("server:\n  graceful_shutdown_timeout: 7\n", encoding="utf-8")
    captured = {}

    def fake_run(app, **kwargs):
        captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "uvicorn", types.SimpleNamespace(run=fake_run))

    main(["--config", str(config_path)])

    assert captured["timeout_graceful_shutdown"] == 7
