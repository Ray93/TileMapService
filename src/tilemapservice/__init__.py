"""TileMapService package."""

# Try to get version from package metadata first
try:
    from importlib.metadata import version, PackageNotFoundError
    __version__ = version("tilemapservice")
except (PackageNotFoundError, Exception):
    # Fallback: read from pyproject.toml
    try:
        import tomllib
        from pathlib import Path
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)
                __version__ = pyproject.get("project", {}).get("version", "0.0.0")
        else:
            __version__ = "0.0.0"
    except Exception:
        __version__ = "0.0.0"
