"""Preview routes."""
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()

# Cache preview HTML content at module level to avoid repeated disk reads
_preview_html_cache: str | None = None


def get_static_base_path() -> Path:
    """Get the base path for static files.

    Priority order:
    1. TILEMAPSERVICE_STATIC_PATH environment variable
    2. Current working directory (for external static/ folder)
    3. _MEIPASS (PyInstaller temp dir)
    4. Executable directory
    5. Source directory (development mode)
    """
    import sys
    import tempfile

    # Check if path was passed via environment variable
    static_path_env_key = "TILEMAPSERVICE_STATIC_PATH"
    if static_path_env_key in os.environ:
        return Path(os.environ[static_path_env_key])

    # Check current working directory first (for external static/ folder)
    cwd = Path.cwd()
    if (cwd / "static" / "preview.html").exists():
        return cwd

    # Development mode - use source directory
    if not getattr(sys, 'frozen', False):
        return Path(__file__).parents[2]

    # Frozen mode - check _MEIPASS
    if hasattr(sys, '_MEIPASS'):
        meipass = Path(sys._MEIPASS)
        if (meipass / "static" / "preview.html").exists():
            return meipass

    # Fallback to exe directory
    return Path(sys.executable).parent


def load_preview_html() -> str:
    """Load and cache preview HTML content."""
    global _preview_html_cache

    if _preview_html_cache is None:
        base_path = get_static_base_path()
        # The path should be base_path/static/preview.html
        html_path = base_path / "static" / "preview.html"

        if html_path.exists():
            try:
                _preview_html_cache = html_path.read_text(encoding="utf-8")
            except Exception as e:
                _preview_html_cache = f"<h1>TileMapService Preview</h1><p>Error loading preview template: {e}</p>"
        else:
            # Debug info to help troubleshoot
            _preview_html_cache = f"<h1>TileMapService Preview</h1><p>Preview template not found.</p><p>Looking for: {html_path}</p><p>Base path: {base_path}</p>"

    return _preview_html_cache


@router.get("/")
async def index():
    return RedirectResponse(url="/preview")


@router.get(
    "/preview",
    tags=["预览"],
    summary="获取交互式地图预览页面",
    description="返回基于Leaflet的交互式地图预览HTML页面，可用于测试和可视化瓦片服务",
    response_class=HTMLResponse
)
async def preview_home():
    return load_preview_html()


@router.get(
    "/preview/{source}",
    tags=["预览"],
    summary="获取特定数据源的预览页面",
    description="返回指定数据源的Leaflet预览页面，URL参数会自动填充到地图配置中",
    response_class=HTMLResponse
)
async def preview_source(source: str):
    return await preview_home()
