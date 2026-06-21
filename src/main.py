"""TileMapService application entrypoint."""
import sys
import os
from pathlib import Path

# Import version from package
from tilemapservice import __version__

# CRITICAL: Set PROJ_DATA environment variable FIRST, before any other imports
# This must run before pyproj is imported (even indirectly through tilemapservice modules)
# because pyproj initializes the PROJ library on first import and caches the database path.
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # PyInstaller frozen mode: set PROJ_DATA to _MEIPASS location
    meipass = Path(sys._MEIPASS)
    proj_data_dir = meipass / "pyproj" / "proj_dir" / "share" / "proj"
    if proj_data_dir.exists():
        os.environ['PROJ_DATA'] = str(proj_data_dir)
        os.environ['PROJ_LIB'] = str(proj_data_dir)
        # Also try to set it via pyproj API (after pyproj is imported)
        # This will be done again in create_app() after pyproj is definitely imported

# Now import everything else
import argparse
import atexit
import ctypes
import shutil
import signal
import subprocess
import tempfile
import time
from contextlib import asynccontextmanager
from datetime import datetime

import yaml
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tilemapservice.api.routes import api_router
from tilemapservice.models.config import AppConfig
from tilemapservice.services.bundle_pool import BundlePool
from tilemapservice.services.cache import TileCache
from tilemapservice.services.capabilities_builder import CapabilitiesBuilder
from tilemapservice.services.sharded_cache import ShardedTileCache
from tilemapservice.services.source_manager import SourceManager
from tilemapservice.services.tile_service import TileService
from tilemapservice.utils.logger import setup_logger
from tilemapservice.utils.stats import RequestStats

# CRITICAL: After all imports, try to force pyproj to use the correct data directory
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    try:
        import pyproj
        meipass = Path(sys._MEIPASS)
        proj_data_dir = meipass / "pyproj" / "proj_dir" / "share" / "proj"
        if proj_data_dir.exists():
            pyproj.datadir.set_data_dir(str(proj_data_dir))
    except Exception:
        pass  # Will log in create_app


# PID file for daemon process management
PID_FILE_NAME = "tilemapservice.pid"


def get_static_base_path() -> Path:
    """Get the base path for static files.

    Priority order:
    1. Current working directory (for external static/ folder)
    2. _MEIPASS (PyInstaller temp dir)
    3. _internal directory (onedir mode)
    4. Executable directory
    5. Source directory (development mode)
    """
    # Check current working directory first (for external static/ folder)
    cwd = Path.cwd()
    if (cwd / "static").exists():
        return cwd

    # Development mode - use source directory (project root)
    if not getattr(sys, 'frozen', False):
        return Path(__file__).parent

    # Frozen mode (PyInstaller)
    # Onefile mode: _MEIPASS exists and is temporary
    if hasattr(sys, '_MEIPASS'):
        meipass = Path(sys._MEIPASS)
        if (meipass / "static").exists():
            return meipass

    # Onedir mode: static/ is in _internal/ next to executable
    exe_dir = Path(sys.executable).parent
    internal_dir = exe_dir / "_internal"
    if internal_dir.exists():
        return internal_dir

    # Fallback
    return exe_dir


def get_exe_dir() -> Path:
    """Get the directory where the executable or script resides."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_pid_file() -> Path:
    """Get the PID file path.

    Uses current working directory for PID file to ensure:
    - Status command can find it from same directory
    - Works with staticx where exe_dir is temporary
    """
    return Path.cwd() / PID_FILE_NAME


def write_pid_file():
    """Write current process PID to file."""
    pid_file = get_pid_file()
    pid_file.write_text(str(os.getpid()))
    atexit.register(remove_pid_file)


def remove_pid_file():
    """Remove PID file on exit."""
    pid_file = get_pid_file()
    if pid_file.exists():
        pid_file.unlink()


def read_pid() -> int | None:
    """Read PID from file, return None if not exists or invalid."""
    pid_file = get_pid_file()
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
        return pid
    except (ValueError, IOError, PermissionError):
        return None


def is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running."""
    if sys.platform == 'win32':
        try:
            # Use OpenProcess for reliable check instead of tasklist parsing
            PROCESS_QUERY_INFORMATION = 0x0400
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def get_exe_path() -> str:
    """Get the executable path."""
    if getattr(sys, 'frozen', False):
        return sys.executable
    return sys.argv[0]


def hide_console_window():
    """Hide the console window on Windows."""
    if sys.platform == 'win32':
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(), 0  # SW_HIDE
        )


def setup_daemon_logging():
    """Setup logging to file for daemon mode."""
    # Use current working directory for logs (same as PID file)
    logs_dir = Path.cwd() / "logs"

    # Try to create logs directory with error handling
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError) as e:
        # If can't create in CWD, try user's temp directory
        import tempfile
        logs_dir = Path(tempfile.gettempdir()) / "tilemapservice" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        print(f"Warning: Using fallback log directory: {logs_dir}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"tilemapservice_{timestamp}.log"

    # Open log file with explicit buffering
    try:
        log_file_obj = open(log_file, 'a', encoding='utf-8', buffering=1)
    except Exception as e:
        print(f"Failed to open log file: {e}")
        raise

    # Create a filter to suppress PyInstaller warnings
    class SuppressPyInstallerWarnings:
        def __init__(self, stream):
            self.stream = stream

        def write(self, text):
            # Filter out PyInstaller temporary directory warnings
            if 'Failed to remove temporary directory' not in text and '[PYI-' not in text:
                self.stream.write(text)

        def flush(self):
            self.stream.flush()

        def close(self):
            self.stream.close()

    # Wrap stderr with filter
    filtered_log = SuppressPyInstallerWarnings(log_file_obj)

    # Redirect stdout to log file, stderr to filtered log
    sys.stdout = log_file_obj
    sys.stderr = filtered_log

    # Configure logging to use the new stdout
    import logging
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s'
    )

    # Ensure file is flushed and closed on exit
    def cleanup():
        try:
            log_file_obj.flush()
            log_file_obj.close()
        except Exception:
            pass  # Ignore errors during cleanup
    atexit.register(cleanup)

    return log_file


def daemonize():
    """Enter daemon mode: hide console and redirect logs."""
    log_file = setup_daemon_logging()
    write_pid_file()
    hide_console_window()
    print(f"[{datetime.now().isoformat()}] TileMapService started in daemon mode")
    print(f"[{datetime.now().isoformat()}] Log file: {log_file}")
    print(f"[{datetime.now().isoformat()}] PID: {os.getpid()}")
    sys.stdout.flush()
    return log_file


def cmd_status(host: str = "127.0.0.1", port: int = 8000) -> int:
    """Check daemon status."""
    pid = read_pid()
    if pid is None:
        print("TileMapService is not running (no PID file)")
        return 1

    if is_process_running(pid):
        print(f"TileMapService is running (PID: {pid})")
        # Try to check health endpoint
        try:
            import urllib.request
            resp = urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2)
            if resp.status == 200:
                print(f"Health check: OK")
            else:
                print(f"Health check: FAILED (status {resp.status})")
        except Exception as e:
            print(f"Health check: FAILED ({e})")
        return 0
    else:
        print(f"TileMapService is not running (PID file exists but process {pid} not found)")
        remove_pid_file()
        return 1


def cmd_stop() -> int:
    """Stop daemon process."""
    pid = read_pid()
    if pid is None:
        print("TileMapService is not running (no PID file)")
        return 1

    if not is_process_running(pid):
        print(f"TileMapService is not running (process {pid} not found)")
        remove_pid_file()
        return 1

    print(f"Stopping TileMapService (PID: {pid})...")
    try:
        if sys.platform == 'win32':
            # On Windows, use taskkill with /F directly for Python processes
            # Python processes often don't respond to graceful SIGTERM
            subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL,
                          timeout=10)
        else:
            # On Unix, try SIGTERM first
            os.kill(pid, signal.SIGTERM)

        # Wait for process to terminate with exponential backoff
        max_wait = 5  # seconds (reduced since we're using /F)
        check_interval = 0.1
        elapsed = 0.0

        while elapsed < max_wait:
            if not is_process_running(pid):
                break
            time.sleep(check_interval)
            elapsed += check_interval
            check_interval = min(check_interval * 1.5, 0.5)

        if is_process_running(pid):
            print(f"Warning: Process {pid} may still be running")
            return 1

        remove_pid_file()
        print("TileMapService stopped")
        return 0
    except Exception as e:
        print(f"Failed to stop process: {e}")
        return 1


def cmd_start(args: argparse.Namespace) -> int:
    """Start daemon process."""
    pid = read_pid()
    if pid is not None and is_process_running(pid):
        print(f"TileMapService is already running (PID: {pid})")
        return 1

    print(f"Starting TileMapService...")

    # Windows daemon: subprocess.Popen with CREATE_NO_WINDOW (no console window)
    exe_path = get_exe_path()
    start_cwd = os.getcwd()

    # Build command arguments
    cmd_args = [exe_path, '--daemon-internal']
    if args.config:
        cmd_args.extend(['--config', args.config])
    if args.host:
        cmd_args.extend(['--host', args.host])
    if args.port:
        cmd_args.extend(['--port', str(args.port)])
    if hasattr(args, 'debug') and args.debug:
        cmd_args.append('--debug')
    if hasattr(args, 'cache_size') and args.cache_size:
        cmd_args.extend(['--cache-size', str(args.cache_size)])
    if hasattr(args, 'cors') and args.cors:
        cmd_args.append('--cors')
    if hasattr(args, 'graceful_shutdown_timeout') and args.graceful_shutdown_timeout:
        cmd_args.extend(['--graceful-shutdown-timeout', str(args.graceful_shutdown_timeout)])

    try:
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            cmd_args,
            cwd=start_cwd,
            creationflags=CREATE_NO_WINDOW,
            close_fds=True
        )
    except Exception as e:
        print(f"Failed to start TileMapService: {e}")
        return 1

    # Poll for startup
    max_wait = 10
    check_interval = 0.2
    elapsed = 0.0

    while elapsed < max_wait:
        time.sleep(check_interval)
        elapsed += check_interval
        pid = read_pid()
        if pid and is_process_running(pid):
            print(f"TileMapService started (PID: {pid})")
            return 0

    print("TileMapService failed to start. Check logs for details.")
    return 1


def cmd_restart(args: argparse.Namespace) -> int:
    """Restart daemon process."""
    print("Restarting TileMapService...")
    stop_result = cmd_stop()

    # Check if stop was successful before starting
    if stop_result != 0:
        print("Failed to stop existing service, aborting restart")
        return stop_result

    time.sleep(1)
    start_result = cmd_start(args)
    return start_result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tile Map Service")
    parser.add_argument("-v", "-V", "--version", action="version",
                        version=f"TileMapService {__version__}",
                        help="显示版本号并退出")
    parser.add_argument("--host", type=str, default=None, help="服务主机地址")
    parser.add_argument("--port", type=int, default=None, help="服务端口")
    parser.add_argument("--config", type=str, default=default_config_path(), help="配置文件路径")
    parser.add_argument("--debug", action="store_true", default=None, help="调试模式")
    parser.add_argument("--daemon-internal", action="store_true", default=False, help=argparse.SUPPRESS)
    parser.add_argument("--cache-size", type=int, default=None, help="缓存最大瓦片数")
    parser.add_argument("--cors", action="store_true", default=None, help="启用 CORS")
    parser.add_argument("--graceful-shutdown-timeout", type=int, default=None, help="优雅关闭等待秒数")

    # Process management commands (Windows only — Linux uses foreground run;
    # see docs/superpowers/specs/2026-06-18-remove-linux-daemon-design.md)
    subparsers = parser.add_subparsers(dest='command', help='进程管理命令')

    if sys.platform == 'win32':
        # status command
        status_parser = subparsers.add_parser('status', help='查看服务状态')
        status_parser.add_argument("--host", type=str, default="127.0.0.1", help="服务主机地址")
        status_parser.add_argument("--port", type=int, default=8000, help="服务端口")

        # stop command
        subparsers.add_parser('stop', help='停止后台服务')

        # start command (with same options as main parser)
        start_parser = subparsers.add_parser('start', help='启动后台服务')
        start_parser.add_argument("--host", type=str, default=None, help="服务主机地址")
        start_parser.add_argument("--port", type=int, default=None, help="服务端口")
        start_parser.add_argument("--config", type=str, default=default_config_path(), help="配置文件路径")
        start_parser.add_argument("--debug", action="store_true", default=None, help="调试模式")
        start_parser.add_argument("--cache-size", type=int, default=None, help="缓存最大瓦片数")
        start_parser.add_argument("--cors", action="store_true", default=None, help="启用 CORS")
        start_parser.add_argument("--graceful-shutdown-timeout", type=int, default=None, help="优雅关闭等待秒数")

        # restart command
        restart_parser = subparsers.add_parser('restart', help='重启后台服务')
        restart_parser.add_argument("--host", type=str, default=None, help="服务主机地址")
        restart_parser.add_argument("--port", type=int, default=None, help="服务端口")
        restart_parser.add_argument("--config", type=str, default=default_config_path(), help="配置文件路径")
        restart_parser.add_argument("--debug", action="store_true", default=None, help="调试模式")
        restart_parser.add_argument("--cache-size", type=int, default=None, help="缓存最大瓦片数")
        restart_parser.add_argument("--cors", action="store_true", default=None, help="启用 CORS")
        restart_parser.add_argument("--graceful-shutdown-timeout", type=int, default=None, help="优雅关闭等待秒数")

    if sys.platform == 'linux':
        service_parser = subparsers.add_parser('service', help='systemd 服务管理')
        service_subparsers = service_parser.add_subparsers(dest='service_command')
        service_subparsers.required = True

        install_parser = service_subparsers.add_parser('install', help='安装 systemd 服务')
        install_parser.add_argument("--host", type=str, default=None, help="服务主机地址（未指定时不写入 ExecStart）")
        install_parser.add_argument("--port", type=int, default=None, help="服务端口（未指定时不写入 ExecStart）")
        install_parser.add_argument("--config", type=str, default=None, help="配置文件路径（默认：安装目录/config.yaml）")
        install_parser.add_argument("--user", type=str, default="root", help="服务运行账号（默认 root）")
        install_parser.add_argument("--force", action="store_true", help="已存在服务时直接覆盖并重启")

        service_subparsers.add_parser('uninstall', help='卸载 systemd 服务')
        service_subparsers.add_parser('status', help='查看 systemd 服务状态')
        service_subparsers.add_parser('start', help='启动 systemd 服务')
        service_subparsers.add_parser('stop', help='停止 systemd 服务')
        service_subparsers.add_parser('restart', help='重启 systemd 服务')
        logs_parser = service_subparsers.add_parser('logs', help='查看 journald 日志')
        logs_parser.add_argument("-n", "--lines", type=int, default=50, help="显示日志行数（默认 50）")
        logs_parser.add_argument("-f", "--follow", action="store_true", help="持续跟随日志输出")

    return parser.parse_args(argv)


def parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"invalid boolean value: {value}")


def parse_env_value(current, value: str):
    if isinstance(current, bool):
        return parse_bool(value)
    if isinstance(current, int):
        return int(value)
    if isinstance(current, float):
        return float(value)
    if isinstance(current, list):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def default_config_path() -> str:
    """Config file path from TILEMAPSERVICE_CONFIG, falling back to config.yaml."""
    return os.getenv("TILEMAPSERVICE_CONFIG", "config.yaml")


def _resolve_env_path(obj: BaseModel, parts: list[str], value: str) -> bool:
    """Apply one env override by longest-matching segments against model fields.

    ``parts`` is the env-var name split on ``_`` after the ``TILEMAPSERVICE_``
    prefix, e.g. ``["bundle", "pool", "max", "size"]`` or
    ``["defaults", "spatial", "ref", "wkid"]``. Underscore-bearing field names
    (``bundle_pool``, ``graceful_shutdown_timeout``) are matched by trying the
    longest segment prefix first, then descending into nested models.

    Returns True if a leaf field was set, False if no field matched or the path
    tries to descend into a scalar.
    """
    fields = type(obj).model_fields
    for k in range(len(parts), 0, -1):
        name = "_".join(parts[:k])
        if name not in fields:
            continue
        current = getattr(obj, name)
        remaining = parts[k:]
        if not remaining:
            setattr(obj, name, parse_env_value(current, value))
            return True
        if isinstance(current, BaseModel):
            return _resolve_env_path(current, remaining, value)
        return False
    return False


def load_config(config_path: str = "config.yaml") -> AppConfig:
    config_data = {}
    if Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as file:
            config_data = yaml.safe_load(file) or {}
    config = AppConfig(**config_data)

    prefix = "TILEMAPSERVICE_"
    for key, value in os.environ.items():
        if not key.startswith(prefix) or key == "TILEMAPSERVICE_CONFIG":
            continue
        parts = key[len(prefix) :].lower().split("_")
        # 'sources' is a list of objects and cannot be represented as a single
        # env var; configure data sources via the config file instead.
        if parts[0] == "sources":
            continue
        _resolve_env_path(config, parts, value)
    return config


def apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    if args.host:
        config.server.host = args.host
    if args.port:
        config.server.port = args.port
    if args.debug is not None:
        config.server.debug = args.debug
    if args.cache_size:
        config.cache.max_size = args.cache_size
    if args.cors is not None:
        config.cors.enabled = args.cors
    if args.graceful_shutdown_timeout is not None:
        config.server.graceful_shutdown_timeout = args.graceful_shutdown_timeout
    return config


# OpenAPI tags for endpoint grouping
tags_metadata = [
    {
        "name": "瓦片服务",
        "description": "XYZ、TMS、Source Matrix 瓦片请求。支持多种坐标系和输出格式。",
    },
    {
        "name": "WMTS",
        "description": "OGC WMTS 1.0.0 标准服务。提供 GetCapabilities 和 GetTile 操作。",
    },
    {
        "name": "元数据",
        "description": "数据源信息查询。获取可用数据源列表和详细配置。",
    },
    {
        "name": "监控",
        "description": "服务健康检查和统计信息。用于监控和运维。",
    },
    {
        "name": "预览",
        "description": "Web 预览界面。提供地图可视化和快速测试。",
    },
]


def create_app(config: AppConfig) -> FastAPI:
    logger = setup_logger()

    # CRITICAL: Force pyproj to use correct PROJ data directory in frozen mode
    # Must be done after pyproj is imported but before any CRS objects are created
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        import pyproj
        meipass = Path(sys._MEIPASS)
        proj_data_dir = meipass / "pyproj" / "proj_dir" / "share" / "proj"
        if proj_data_dir.exists() and (proj_data_dir / "proj.db").exists():
            # Set environment variables and force pyproj to reload data directory
            os.environ['PROJ_DATA'] = str(proj_data_dir)
            os.environ['PROJ_LIB'] = str(proj_data_dir)
            try:
                pyproj.datadir.set_data_dir(str(proj_data_dir))
            except Exception as e:
                logger.error(f"Failed to set pyproj data dir: {e}")

    # Pre-import modules that FileResponse needs (for staticx compatibility)
    # This ensures they're loaded while staticx temp directory still exists
    try:
        # Core anyio modules
        import anyio
        import anyio._core._eventloop
        import anyio.to_thread
        import anyio.abc
        import anyio._backends
        import anyio._backends._asyncio

        # sniffio is required by anyio - will be loaded by anyio automatically
        try:
            import sniffio
        except ImportError:
            pass  # sniffio will be loaded dynamically by anyio if needed
    except ImportError:
        pass  # Modules will load dynamically when needed

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("TileMapService starting")
        app.state.source_manager.load_sources(config.sources)

        # Create Bundle pool if enabled
        if config.bundle_pool.enabled:
            app.state.bundle_pool = BundlePool(max_size=config.bundle_pool.max_size)
            logger.info(f"Bundle pool initialized (max_size={config.bundle_pool.max_size})")
        else:
            app.state.bundle_pool = None
            logger.info("Bundle pool disabled")

        # Create TileService with bundle_pool
        app.state.tile_service = TileService(
            source_manager=app.state.source_manager,
            cache=app.state.cache,
            stats=app.state.stats,
            bundle_pool=app.state.bundle_pool
        )

        # Build and cache WMTS capabilities
        if config.server.service_url:
            service_url = config.server.service_url
        else:
            service_url = f"http://{config.server.host}:{config.server.port}"
        sources = app.state.source_manager.list_all()
        builder = CapabilitiesBuilder(sources, service_url)
        app.state.wmts_capabilities = builder.generate()
        logger.info(f"WMTS capabilities generated for {len(sources)} sources")

        yield

        # Close bundle pool
        if app.state.bundle_pool:
            app.state.bundle_pool.close_all()
            logger.info("Bundle pool closed")

        # Clear capabilities cache on shutdown
        app.state.wmts_capabilities = None
        logger.info("TileMapService stopped")

    app = FastAPI(
        title="TileMapService API",
        version=__version__,
        description=(
            "高性能离线瓦片地图服务，支持 ESRI ArcGIS Compact Cache (V1/V2) 数据读取和发布。\n\n"
            "支持的功能：\n"
            "- XYZ/TMS 瓦片服务\n"
            "- WMTS 1.0.0 标准协议\n"
            "- 多坐标系支持 (EPSG:3857, EPSG:4326)\n"
            "- PNG/JPEG 格式输出\n"
            "- 内置缓存机制"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=tags_metadata,
        lifespan=lifespan,
    )

    if config.cors.enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors.allow_origins,
            allow_methods=config.cors.allow_methods,
            allow_headers=config.cors.allow_headers,
        )

    # Initialize cache (sharded if num_shards > 1, otherwise single cache)
    if config.cache.num_shards > 1:
        cache = ShardedTileCache(
            enabled=config.cache.enabled,
            max_size=config.cache.max_size,
            ttl=config.cache.ttl,
            num_shards=config.cache.num_shards
        )
    else:
        cache = TileCache(enabled=config.cache.enabled, max_size=config.cache.max_size, ttl=config.cache.ttl)
    source_manager = SourceManager(config.defaults)
    known_sources = {src.name for src in config.sources}
    stats = RequestStats(known_sources=known_sources)
    app.state.cache = cache
    app.state.source_manager = source_manager
    app.state.stats = stats
    app.state.config = config
    app.include_router(api_router)

    # Mount static libs directory for Leaflet and other libraries
    # Use a simple route instead of StaticFiles to avoid import issues in frozen mode
    from fastapi import APIRouter
    from fastapi.responses import FileResponse, Response

    libs_router = APIRouter()

    @libs_router.get("/libs/{file_path:path}")
    async def serve_libs(file_path: str):
        """Serve static library files."""
        try:
            # Calculate path dynamically for each request (onefile/staticx
            # resolve to different base dirs; per-request lookup is robust)
            base_path = get_static_base_path()
            libs_path = (base_path / "static" / "libs").resolve()
            full_path = (libs_path / file_path).resolve()

            if not full_path.is_relative_to(libs_path):
                return Response(status_code=404)

            if full_path.exists() and full_path.is_file():
                # Read file manually instead of using FileResponse
                # FileResponse uses anyio.to_thread which causes delayed imports in staticx
                with open(full_path, 'rb') as f:
                    content = f.read()

                # Determine content type
                suffix = full_path.suffix.lower()
                content_types = {
                    '.css': 'text/css',
                    '.js': 'application/javascript',
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif',
                    '.svg': 'image/svg+xml',
                }
                media_type = content_types.get(suffix, 'application/octet-stream')

                # Return Response with content directly
                return Response(content=content, media_type=media_type)

            return Response(status_code=404)
        except Exception as e:
            import logging
            logger = logging.getLogger("tilemapservice")
            logger.error(f"Error serving libs file {file_path}: {e}", exc_info=True)
            logger.error(f"CWD: {Path.cwd()}, base_path: {get_static_base_path()}")
            return Response(status_code=500, content=f"Internal error: {str(e)}")

    app.include_router(libs_router)

    return app


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    args = parse_args(argv)

    # Handle process management commands BEFORE any heavy initialization
    if args.command == 'status':
        # Pass host/port from args if provided
        host = getattr(args, 'host', '127.0.0.1')
        port = getattr(args, 'port', 8000)
        sys.exit(cmd_status(host, port))
    elif args.command == 'stop':
        sys.exit(cmd_stop())
    elif args.command == 'start':
        sys.exit(cmd_start(args))
    elif args.command == 'restart':
        sys.exit(cmd_restart(args))

    # systemd service management (Linux only)
    if args.command == 'service':
        from tilemapservice.systemd_manager import (
            install_service,
            logs_service,
            restart_service,
            start_service,
            status_service,
            stop_service,
            uninstall_service,
        )

        if args.service_command == 'install':
            sys.exit(install_service(
                host=args.host,
                port=args.port,
                config_path=args.config,
                user=args.user,
                force=args.force,
            ))
        elif args.service_command == 'uninstall':
            sys.exit(uninstall_service())
        elif args.service_command == 'status':
            sys.exit(status_service())
        elif args.service_command == 'start':
            sys.exit(start_service())
        elif args.service_command == 'stop':
            sys.exit(stop_service())
        elif args.service_command == 'restart':
            sys.exit(restart_service())
        elif args.service_command == 'logs':
            sys.exit(logs_service(lines=args.lines, follow=args.follow))

    # Internal daemon mode (spawned by 'start' command)
    if args.daemon_internal:
        daemonize()

    # Run server in foreground mode
    cli_config = apply_cli_overrides(load_config(args.config), args)
    uvicorn.run(
        create_app(cli_config),
        host=cli_config.server.host,
        port=cli_config.server.port,
        log_level="debug" if cli_config.server.debug else "info",
        timeout_graceful_shutdown=cli_config.server.graceful_shutdown_timeout,
    )


# Module-level initialization moved INSIDE main() to avoid early errors
# Do NOT load config at module level - it prevents proper error logging in daemon mode
if __name__ == "__main__":
    main()
