import sys
import types

from fastapi.testclient import TestClient

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


def test_apply_cli_overrides_preserves_config_when_flags_omitted():
    args = parse_args([])
    config = AppConfig()
    config.cors.enabled = True
    config.server.debug = True

    overridden = apply_cli_overrides(config, args)

    assert overridden.cors.enabled is True
    assert overridden.server.debug is True


def test_main_passes_finite_graceful_shutdown_timeout_to_uvicorn(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("server:\n  graceful_shutdown_timeout: 7\n", encoding="utf-8")
    captured = {}

    def fake_run(app, **kwargs):
        captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "uvicorn", types.SimpleNamespace(run=fake_run))

    main(["--config", str(config_path)])

    assert captured["timeout_graceful_shutdown"] == 7


def test_libs_route_blocks_path_traversal(tmp_path, monkeypatch):
    static_libs = tmp_path / "static" / "libs"
    static_libs.mkdir(parents=True)
    (static_libs / "ok.js").write_text("console.log('ok')", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from main import create_app

    app = create_app(AppConfig())
    client = TestClient(app)

    ok = client.get("/libs/ok.js")
    assert ok.status_code == 200
    assert ok.text == "console.log('ok')"

    traversal = client.get("/libs/%2e%2e/%2e%2e/secret.txt")
    assert traversal.status_code == 404
