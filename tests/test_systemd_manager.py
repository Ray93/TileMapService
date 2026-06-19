import subprocess
import sys
import types
from pathlib import Path

import pytest

from tilemapservice import systemd_manager as sm


def completed(args, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def linux_systemd_env(monkeypatch, tmp_path):
    deploy_dir = tmp_path / "deploy"
    deploy_dir.mkdir()
    (deploy_dir / "static").mkdir()
    (deploy_dir / "config.yaml").write_text("server:\n  port: 8000\n", encoding="utf-8")

    unit_path = tmp_path / "systemd" / "tilemapservice.service"
    unit_path.parent.mkdir()
    runtime_dir = tmp_path / "run" / "systemd" / "system"
    runtime_dir.mkdir(parents=True)

    monkeypatch.chdir(deploy_dir)
    monkeypatch.setattr(sm.sys, "platform", "linux")
    monkeypatch.setattr(sm.sys, "argv", ["./TileMapService"])
    monkeypatch.setattr(sm.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(
        sm.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"systemctl", "journalctl"} else None,
    )
    monkeypatch.setattr(sm, "SERVICE_UNIT_PATH", unit_path)
    monkeypatch.setattr(sm, "SYSTEMD_RUNTIME_DIR", runtime_dir)
    monkeypatch.setitem(sys.modules, "pwd", types.SimpleNamespace(getpwnam=lambda user: object()))

    return {
        "deploy_dir": deploy_dir,
        "unit_path": unit_path,
        "runtime_dir": runtime_dir,
    }


def test_generate_unit_contains_required_fields_and_no_group(tmp_path):
    unit = sm._generate_unit(
        install_dir=tmp_path,
        binary_name="TileMapService",
        config_path=tmp_path / "config.yaml",
        extra_args=["--host", "0.0.0.0", "--port", "8080"],
        user="tilemap",
    )

    assert "Wants=network-online.target" in unit
    assert "After=network-online.target" in unit
    assert "User=tilemap" in unit
    assert "Group=" not in unit
    assert f"WorkingDirectory={tmp_path}" in unit
    assert f"ExecStart={tmp_path / 'TileMapService'} --config {tmp_path / 'config.yaml'} --host 0.0.0.0 --port 8080" in unit
    assert "StartLimitIntervalSec=60" in unit
    assert "StartLimitBurst=5" in unit
    assert "KillSignal=SIGTERM" in unit
    assert "TimeoutStopSec=120" in unit
    assert "NoNewPrivileges=true" in unit
    assert "[Install]" in unit
    assert "WantedBy=multi-user.target" in unit


def test_resolve_install_dir_uses_cwd_and_argv_not_sys_executable(linux_systemd_env, monkeypatch):
    monkeypatch.setattr(sm.sys, "executable", "/tmp/staticx-abc/TileMapService")
    install_dir, binary_name = sm._resolve_install_dir()

    assert install_dir == linux_systemd_env["deploy_dir"].resolve()
    assert binary_name == "TileMapService"


def test_resolve_install_dir_rejects_non_deploy_dir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sm.sys, "argv", ["./TileMapService"])

    with pytest.raises(sm.SystemdManagerError):
        sm._resolve_install_dir()


def test_resolve_config_path_defaults_to_install_config(tmp_path):
    assert sm._resolve_config_path(None, tmp_path) == (tmp_path / "config.yaml").resolve()
    assert sm._resolve_config_path("custom.yaml", tmp_path) == (tmp_path / "custom.yaml").resolve()


def test_validate_no_spaces_rejects_paths_with_spaces():
    with pytest.raises(sm.SystemdManagerError):
        sm._validate_no_spaces(Path("/opt/Tile Map Service"))


def test_install_service_writes_unit_and_runs_enable_start(linux_systemd_env, monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return completed(cmd)

    monkeypatch.setattr(sm.subprocess, "run", fake_run)
    monkeypatch.setattr(sm, "_check_service_active", lambda: False)
    monkeypatch.setattr(sm, "_wait_active", lambda timeout: True)

    result = sm.install_service(host="0.0.0.0", port=8080, user="root")

    assert result == 0
    unit_text = linux_systemd_env["unit_path"].read_text(encoding="utf-8")
    assert "--host 0.0.0.0 --port 8080" in unit_text
    assert "--config " in unit_text
    assert "Group=" not in unit_text
    assert "[Install]" in unit_text
    assert calls == [
        ["systemctl", "daemon-reload"],
        ["systemctl", "enable", "tilemapservice"],
        ["systemctl", "start", "tilemapservice"],
    ]


def test_install_service_does_not_bake_unspecified_host_port(linux_systemd_env, monkeypatch):
    monkeypatch.setattr(sm.subprocess, "run", lambda cmd, capture_output, text: completed(cmd))
    monkeypatch.setattr(sm, "_check_service_active", lambda: False)
    monkeypatch.setattr(sm, "_wait_active", lambda timeout: True)

    result = sm.install_service(user="root")

    assert result == 0
    unit_text = linux_systemd_env["unit_path"].read_text(encoding="utf-8")
    exec_start_line = next(line for line in unit_text.splitlines() if line.startswith("ExecStart="))
    assert "--config" in exec_start_line
    assert "--host" not in exec_start_line
    assert "--port" not in exec_start_line


def test_install_existing_unit_requires_force(linux_systemd_env, monkeypatch):
    linux_systemd_env["unit_path"].write_text("old", encoding="utf-8")
    monkeypatch.setattr(sm.subprocess, "run", lambda cmd, capture_output, text: completed(cmd))
    monkeypatch.setattr(sm, "_check_service_active", lambda: False)

    result = sm.install_service(user="root")

    assert result == 1
    assert linux_systemd_env["unit_path"].read_text(encoding="utf-8") == "old"


def test_force_install_overwrites_and_restarts(linux_systemd_env, monkeypatch):
    linux_systemd_env["unit_path"].write_text("old", encoding="utf-8")
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return completed(cmd)

    monkeypatch.setattr(sm.subprocess, "run", fake_run)
    monkeypatch.setattr(sm, "_check_service_active", lambda: False)
    monkeypatch.setattr(sm, "_wait_active", lambda timeout: True)

    result = sm.install_service(user="root", force=True)

    assert result == 0
    assert "Description=TileMapService" in linux_systemd_env["unit_path"].read_text(encoding="utf-8")
    assert calls == [
        ["systemctl", "stop", "tilemapservice"],
        ["systemctl", "reset-failed", "tilemapservice"],
        ["systemctl", "daemon-reload"],
        ["systemctl", "restart", "tilemapservice"],
    ]


def test_uninstall_removes_unit_and_resets_only_tilemapservice(linux_systemd_env, monkeypatch):
    linux_systemd_env["unit_path"].write_text("unit", encoding="utf-8")
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return completed(cmd)

    monkeypatch.setattr(sm.subprocess, "run", fake_run)

    result = sm.uninstall_service()

    assert result == 0
    assert not linux_systemd_env["unit_path"].exists()
    assert calls == [
        ["systemctl", "stop", "tilemapservice"],
        ["systemctl", "disable", "tilemapservice"],
        ["systemctl", "daemon-reload"],
        ["systemctl", "reset-failed", "tilemapservice"],
    ]


def test_status_service_is_readonly_and_does_not_require_root(linux_systemd_env, monkeypatch):
    calls = []
    monkeypatch.setattr(sm.os, "geteuid", lambda: 1000, raising=False)

    def fake_run(cmd, text):
        calls.append(cmd)
        return completed(cmd, returncode=3)

    monkeypatch.setattr(sm, "_run_systemctl_passthrough", lambda args: fake_run(["systemctl", *args], text=True))

    result = sm.status_service()

    assert result == 3
    assert calls == [["systemctl", "status", "tilemapservice", "--no-pager"]]


def test_start_service_starts_and_waits_active(linux_systemd_env, monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return completed(cmd)

    monkeypatch.setattr(sm.subprocess, "run", fake_run)
    monkeypatch.setattr(sm, "_wait_active", lambda timeout: True)

    result = sm.start_service()

    assert result == 0
    assert calls == [["systemctl", "start", "tilemapservice"]]


def test_stop_service_stops_unit(linux_systemd_env, monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return completed(cmd)

    monkeypatch.setattr(sm.subprocess, "run", fake_run)

    result = sm.stop_service()

    assert result == 0
    assert calls == [["systemctl", "stop", "tilemapservice"]]


def test_restart_service_resets_failed_then_restarts(linux_systemd_env, monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return completed(cmd)

    monkeypatch.setattr(sm.subprocess, "run", fake_run)
    monkeypatch.setattr(sm, "_wait_active", lambda timeout: True)

    result = sm.restart_service()

    assert result == 0
    assert calls == [
        ["systemctl", "reset-failed", "tilemapservice"],
        ["systemctl", "restart", "tilemapservice"],
    ]


def test_logs_service_uses_journalctl_and_does_not_require_root(linux_systemd_env, monkeypatch):
    calls = []
    monkeypatch.setattr(sm.os, "geteuid", lambda: 1000, raising=False)

    def fake_run(cmd, text):
        calls.append(cmd)
        return completed(cmd)

    monkeypatch.setattr(sm, "_run_journalctl_passthrough", lambda args: fake_run(["journalctl", *args], text=True))

    result = sm.logs_service(lines=100, follow=True)

    assert result == 0
    assert calls == [["journalctl", "-u", "tilemapservice", "-n", "100", "-f"]]


def test_environment_guards(monkeypatch, tmp_path):
    monkeypatch.setattr(sm.sys, "platform", "win32")
    with pytest.raises(sm.SystemdManagerError):
        sm._check_linux()

    monkeypatch.setattr(sm.sys, "platform", "linux")
    monkeypatch.setattr(sm.os, "geteuid", lambda: 1000, raising=False)
    with pytest.raises(sm.SystemdManagerError):
        sm._check_root()

    runtime_dir = tmp_path / "missing"
    monkeypatch.setattr(sm.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(sm.shutil, "which", lambda name: "/usr/bin/systemctl")
    monkeypatch.setattr(sm, "SYSTEMD_RUNTIME_DIR", runtime_dir)
    with pytest.raises(sm.SystemdManagerError):
        sm._check_systemctl()


def test_check_user_rejects_missing_user(monkeypatch):
    def raise_key_error(user):
        raise KeyError(user)

    monkeypatch.setitem(sys.modules, "pwd", types.SimpleNamespace(getpwnam=raise_key_error))

    with pytest.raises(sm.SystemdManagerError):
        sm._check_user("missing-user")
