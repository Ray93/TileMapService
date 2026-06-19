import sys

import pytest

from main import parse_args


def test_daemon_subcommands_not_registered_on_linux(monkeypatch):
    """Linux 上不应注册 start/stop/status/restart 子命令。

    spec 2026-06-18-remove-linux-daemon-design.md 2.1:子命令仅 Windows 注册,
    Linux 跑这些命令应得到 argparse 原生 invalid choice 报错(SystemExit code 2)。
    """
    monkeypatch.setattr(sys, "platform", "linux")

    with pytest.raises(SystemExit) as exc_info:
        parse_args(["start", "--port", "8080"])

    assert exc_info.value.code == 2


def test_daemon_subcommands_registered_on_windows(monkeypatch):
    """Windows 上应注册 start 子命令(parse_args 不抛 SystemExit)。"""
    monkeypatch.setattr(sys, "platform", "win32")

    args = parse_args(["start", "--port", "8080"])

    assert args.command == "start"
    assert args.port == 8080


def test_service_subcommand_registered_on_linux(monkeypatch):
    """Linux 上应注册 service install 子命令。"""
    monkeypatch.setattr(sys, "platform", "linux")

    args = parse_args(["service", "install", "--port", "8080", "--user", "tilemap"])

    assert args.command == "service"
    assert args.service_command == "install"
    assert args.port == 8080
    assert args.user == "tilemap"


def test_service_status_and_logs_registered_on_linux(monkeypatch):
    """Linux 上应注册 service status/logs 子命令。"""
    monkeypatch.setattr(sys, "platform", "linux")

    status_args = parse_args(["service", "status"])
    logs_args = parse_args(["service", "logs", "-n", "100", "-f"])

    assert status_args.command == "service"
    assert status_args.service_command == "status"
    assert logs_args.service_command == "logs"
    assert logs_args.lines == 100
    assert logs_args.follow is True


def test_service_lifecycle_commands_registered_on_linux(monkeypatch):
    """Linux 上应注册 service start/stop/restart 子命令。"""
    monkeypatch.setattr(sys, "platform", "linux")

    for command in ("start", "stop", "restart"):
        args = parse_args(["service", command])
        assert args.command == "service"
        assert args.service_command == command


def test_service_requires_nested_command_on_linux(monkeypatch):
    """TileMapService service 缺少 install/uninstall 时应由 argparse 报错。"""
    monkeypatch.setattr(sys, "platform", "linux")

    with pytest.raises(SystemExit) as exc_info:
        parse_args(["service"])

    assert exc_info.value.code == 2


def test_service_subcommand_not_registered_on_windows(monkeypatch):
    """Windows 上不应注册 service 子命令。"""
    monkeypatch.setattr(sys, "platform", "win32")

    with pytest.raises(SystemExit) as exc_info:
        parse_args(["service", "install"])

    assert exc_info.value.code == 2
