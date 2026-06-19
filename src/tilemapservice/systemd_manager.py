"""systemd service management for TileMapService."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


SERVICE_NAME = "tilemapservice"
SERVICE_UNIT_PATH = Path("/etc/systemd/system/tilemapservice.service")
SYSTEMD_RUNTIME_DIR = Path("/run/systemd/system")
DEPLOY_MARKERS = ("config.example.yaml", "static")


class SystemdManagerError(RuntimeError):
    """Expected service-management error shown to CLI users."""


class SystemctlError(SystemdManagerError):
    """Raised when a required systemctl command fails."""


def install_service(
    host: str | None = None,
    port: int | None = None,
    config_path: str | None = None,
    user: str = "root",
    force: bool = False,
) -> int:
    """Install or update the TileMapService systemd unit."""
    try:
        _check_linux()
        _check_root()
        _check_user(user)
        _check_systemctl()

        install_dir, binary_name = _resolve_install_dir()
        resolved_config_path = _resolve_config_path(config_path, install_dir)
        _validate_no_spaces(install_dir)
        _validate_no_spaces(resolved_config_path)

        default_config_path = install_dir / "config.yaml"
        if not default_config_path.exists():
            print(f"警告：未找到配置文件 {default_config_path}，服务可能启动失败")

        extra_args: list[str] = []
        if host is not None:
            extra_args.extend(["--host", host])
        if port is not None:
            extra_args.extend(["--port", str(port)])

        unit_text = _generate_unit(
            install_dir=install_dir,
            binary_name=binary_name,
            config_path=resolved_config_path,
            extra_args=extra_args,
            user=user,
        )

        service_exists = _check_service_exists()
        service_active = _check_service_active()

        if service_exists and not force:
            print("服务已存在，使用 `service uninstall` 后重装或加 `--force` 覆盖")
            return 1
        if service_active and not force:
            print("systemd 服务已在运行，先用 `service uninstall` 或 `systemctl stop tilemapservice`，或加 `--force` 覆盖")
            return 1

        if force and service_exists:
            return _force_install(unit_text)

        _write_unit(unit_text)
        _run_systemctl_required(["daemon-reload"])
        _run_systemctl_required(["enable", SERVICE_NAME])
        _run_systemctl_required(["start", SERVICE_NAME])

        if not _wait_active(timeout=10):
            print("启动可能失败，请查看日志：journalctl -u tilemapservice -n 50")
            return 1

        _print_success("已安装并启动 TileMapService systemd 服务")
        return 0
    except SystemdManagerError as exc:
        print(str(exc))
        return 1


def uninstall_service() -> int:
    """Stop, disable and remove the TileMapService systemd unit."""
    try:
        _check_linux()
        _check_root()
        _check_systemctl()

        _run_systemctl(["stop", SERVICE_NAME])
        _run_systemctl(["disable", SERVICE_NAME])

        if SERVICE_UNIT_PATH.exists():
            SERVICE_UNIT_PATH.unlink()
            print(f"已删除 {SERVICE_UNIT_PATH}")

        _run_systemctl_required(["daemon-reload"])
        _run_systemctl(["reset-failed", SERVICE_NAME])
        print("TileMapService systemd 服务已卸载")
        return 0
    except SystemdManagerError as exc:
        print(str(exc))
        return 1
    except OSError as exc:
        print(f"卸载失败：{exc}")
        return 1


def status_service() -> int:
    """Show the TileMapService systemd status."""
    try:
        _check_linux()
        _check_systemctl()
        result = _run_systemctl_passthrough(["status", SERVICE_NAME, "--no-pager"])
        return result.returncode
    except SystemdManagerError as exc:
        print(str(exc))
        return 1


def start_service() -> int:
    """Start the TileMapService systemd unit."""
    try:
        _check_linux()
        _check_root()
        _check_systemctl()
        _run_systemctl_required(["start", SERVICE_NAME])
        if not _wait_active(timeout=10):
            print("启动可能失败，请查看日志：journalctl -u tilemapservice -n 50")
            return 1
        print("TileMapService systemd 服务已启动")
        return 0
    except SystemdManagerError as exc:
        print(str(exc))
        return 1


def stop_service() -> int:
    """Stop the TileMapService systemd unit."""
    try:
        _check_linux()
        _check_root()
        _check_systemctl()
        _run_systemctl_required(["stop", SERVICE_NAME])
        print("TileMapService systemd 服务已停止")
        return 0
    except SystemdManagerError as exc:
        print(str(exc))
        return 1


def restart_service() -> int:
    """Restart the TileMapService systemd unit."""
    try:
        _check_linux()
        _check_root()
        _check_systemctl()
        _run_systemctl(["reset-failed", SERVICE_NAME])
        _run_systemctl_required(["restart", SERVICE_NAME])
        if not _wait_active(timeout=10):
            print("重启可能失败，请查看日志：journalctl -u tilemapservice -n 50")
            return 1
        print("TileMapService systemd 服务已重启")
        return 0
    except SystemdManagerError as exc:
        print(str(exc))
        return 1


def logs_service(lines: int = 50, follow: bool = False) -> int:
    """Show TileMapService journald logs."""
    try:
        _check_linux()
        _check_systemctl()
        _check_journalctl()
        args = ["-u", SERVICE_NAME, "-n", str(lines)]
        if follow:
            args.append("-f")
        else:
            args.append("--no-pager")
        result = _run_journalctl_passthrough(args)
        return result.returncode
    except SystemdManagerError as exc:
        print(str(exc))
        return 1


def _check_linux() -> None:
    if sys.platform != "linux":
        raise SystemdManagerError("service 子命令仅支持 Linux")


def _check_root() -> None:
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None or geteuid() != 0:
        raise SystemdManagerError("需要 root 权限，请使用 sudo ./TileMapService service install")


def _check_user(user: str) -> None:
    try:
        import pwd

        pwd.getpwnam(user)
    except KeyError as exc:
        raise SystemdManagerError(f"指定用户不存在：{user}") from exc
    except ImportError as exc:
        raise SystemdManagerError("当前平台不支持 Linux 用户查询") from exc


def _check_systemctl() -> None:
    if shutil.which("systemctl") is None:
        raise SystemdManagerError("需要 systemd：未找到 systemctl")
    if not SYSTEMD_RUNTIME_DIR.exists():
        raise SystemdManagerError("需要 systemd：/run/systemd/system 不存在")


def _check_journalctl() -> None:
    if shutil.which("journalctl") is None:
        raise SystemdManagerError("需要 journald：未找到 journalctl")


def _check_service_exists() -> bool:
    return SERVICE_UNIT_PATH.exists()


def _check_service_active() -> bool:
    result = _run_systemctl(["is-active", SERVICE_NAME])
    return result.returncode == 0 and result.stdout.strip() == "active"


def _resolve_install_dir() -> tuple[Path, str]:
    install_dir = Path.cwd().resolve()
    if not any((install_dir / marker).exists() for marker in DEPLOY_MARKERS):
        markers = "/".join(DEPLOY_MARKERS)
        raise SystemdManagerError(f"请在部署目录下执行 install（缺少 {markers}）")

    binary_name = Path(sys.argv[0]).absolute().name
    if not binary_name:
        raise SystemdManagerError("无法解析当前二进制名称")
    return install_dir, binary_name


def _resolve_config_path(config_path: str | None, install_dir: Path) -> Path:
    if config_path is None:
        return (install_dir / "config.yaml").resolve()

    path = Path(config_path)
    if path.is_absolute():
        return path.resolve()
    return (install_dir / path).resolve()


def _validate_no_spaces(path: Path) -> None:
    if " " in str(path):
        raise SystemdManagerError("当前版本暂不支持含空格路径，请迁移到无空格目录后重试")


def _generate_unit(
    install_dir: Path,
    binary_name: str,
    config_path: Path,
    extra_args: list[str],
    user: str,
) -> str:
    exec_parts = [str(install_dir / binary_name), "--config", str(config_path), *extra_args]
    exec_start = " ".join(exec_parts)
    return f"""[Unit]
Description=TileMapService - Offline Tile Publishing Service
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User={user}
WorkingDirectory={install_dir}
ExecStart={exec_start}
Restart=on-failure
RestartSec=3
StartLimitIntervalSec=60
StartLimitBurst=5
KillSignal=SIGTERM
TimeoutStopSec=120
NoNewPrivileges=true
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tilemapservice

[Install]
WantedBy=multi-user.target
"""


def _write_unit(unit_text: str) -> None:
    try:
        SERVICE_UNIT_PATH.write_text(unit_text, encoding="utf-8")
    except OSError as exc:
        raise SystemdManagerError(f"写入 systemd unit 失败：{exc}") from exc


def _force_install(unit_text: str) -> int:
    _run_systemctl(["stop", SERVICE_NAME])
    _run_systemctl(["reset-failed", SERVICE_NAME])
    _write_unit(unit_text)
    _run_systemctl_required(["daemon-reload"])
    _run_systemctl_required(["restart", SERVICE_NAME])

    if not _wait_active(timeout=10):
        print("启动可能失败，请查看日志：journalctl -u tilemapservice -n 50")
        return 1

    _print_success("已覆盖并重启 TileMapService systemd 服务")
    return 0


def _wait_active(timeout: float = 10, interval: float = 0.2) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _check_service_active():
            return True
        time.sleep(interval)
    return False


def _run_systemctl(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", *args],
        capture_output=True,
        text=True,
    )


def _run_systemctl_required(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = _run_systemctl(args)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or f"systemctl {' '.join(args)} failed"
        raise SystemctlError(stderr)
    return result


def _run_systemctl_passthrough(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["systemctl", *args], text=True)


def _run_journalctl_passthrough(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["journalctl", *args], text=True)


def _print_success(message: str) -> None:
    print(message)
    print("常用命令：")
    print("  ./TileMapService service status")
    print("  ./TileMapService service logs -n 50")
    print("  sudo ./TileMapService service restart")
