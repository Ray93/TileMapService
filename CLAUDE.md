# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TileMapService is a FastAPI-based offline tile publishing service that reads ESRI ArcGIS Compact Cache (V1/V2) data and publishes it as XYZ, TMS, WMTS, and CRS matrix tile services.

## Common Commands

```bash
# Install dependencies
uv sync

# Install package in editable mode (optional, improves version lookup performance)
uv pip install -e .

# Install build tools (for packaging)
uv sync --group build

# Show version (works with or without editable install)
uv run python src/main.py --version  # or -v, -V

# Run the service
uv run python src/main.py --port 8000

# Install Linux systemd service from packaged deployment directory
cd /opt/TileMapService
sudo ./TileMapService service install --port 8000
./TileMapService service status
./TileMapService service logs -n 50
sudo ./TileMapService service restart
sudo ./TileMapService service uninstall

# Run tests
uv run pytest tests/ -v

# Run integration tests (requires sample data)
$env:TILEMAPSERVICE_SAMPLE_DATA='path/to/sample-data'
uv run pytest tests/ -v

# Build Windows package (onedir mode)
.\scripts\build-windows.ps1
# Output: dist/TileMapService/ + TileMapService-v<version>-windows-x86_64.tar.gz (or .zip)

# Build Linux package (Docker)
.\scripts\build-linux.ps1  # Windows
./scripts/build-linux.sh   # Linux/macOS
# Output: dist-linux/TileMapService/ + TileMapService-v<version>-linux-x86_64.tar.gz

# Build Linux compatible version (PyInstaller onefile + staticx)
.\scripts\build-linux-staticx.ps1  # Windows
./scripts/build-linux-staticx.sh   # Linux/macOS
# Output: dist-static/TileMapService/ (onefile executable + external static files)
# Note: Linux runs foreground or systemd-managed (no fork daemon); staticx temp dir lives with main process
# Note: Includes pyproj PROJ database files via collect_all('pyproj')
# Compatible with CentOS 7.0+ (glibc 2.17+)

# Docker run
cd docker && docker compose up --build
```

## Architecture

### Request Flow

```
HTTP Request → API Router → TileService → TileLocator → BundlePool → BundleReader → ShardedCache → ImageFormatter → Response
                              ↑               ↑             ↑              ↑
                         SourceManager    TileMatrixSet  file handles    16 shards
```

### Core Components

**API Layer** (`tilemapservice/api/`):
- `routes.py` - Router registration
- `tiles.py` - XYZ/TMS/CRS tile requests
- `wmts.py` + `wmts_exception.py` - WMTS 1.0.0 service
- `metadata.py` - Data source info
- `preview.py` - Leaflet map preview
- `stats.py` - Performance metrics

**Services** (`tilemapservice/services/`):
- `tile_service.py` - Orchestrates tile lookup, caching, formatting
- `tile_locator.py` - Converts request coords to source-native tile indices
- `source_manager.py` - Loads sources, parses Conf.xml/conf.cdi
- `cache.py` - TTL + LRU cache base
- `sharded_cache.py` - 16-shard lock-striped cache for high concurrency
- `bundle_pool.py` - File handle pool (max 50) to reduce IO overhead
- `image_formatter.py` - PNG/JPEG/auto format conversion
- `capabilities_builder.py` + `wmts_service.py` - WMTS Capabilities XML

**API Response Structure**:
- `/api/sources/{name}` returns:
  - `tile_info`: Tile scheme, level definitions (backward compatible)
  - `tile_matrix`: CRS metadata for arbitrary EPSG preview
    - `crs`: EPSG code (e.g., "EPSG:4490")
    - `proj4`: Proj4 definition string
    - `wkt`: WKT definition
    - `is_geographic`: Boolean flag
    - `resolutions`: Array of resolutions for each zoom level
    - `origin`: Tile origin coordinates
    - `tile_size`: Tile size in pixels

**Readers** (`tilemapservice/readers/`):
- `bundle_reader.py` - ArcGIS Compact Cache V1 (.bundle+.bundlx) and V2 (single .bundle)
- `conf_parser.py` - Conf.xml (WKID, TileOrigin, LODs)
- `cdi_parser.py` - conf.cdi (data bounds)

### Bundle File Formats

- **V1**: `.bundle` + `.bundlx` pair. Index in `.bundlx`: 16-byte header + 16384 × 5-byte entries. Tile index: `col × 128 + row` (column-major).
- **V2**: Single `.bundle`. Embedded index: 64-byte header + 16384 × 8-byte entries. Tile index: `row × 128 + col` (row-major). Length stored at `offset - 4`.

### Coordinate Systems

- XYZ: Web Mercator (EPSG:3857), Y axis top-down
- TMS: Y axis inverted (bottom-up)
- Source Matrix: Native CRS of data source (supports any EPSG code)
- Geographic Matrix: EPSG:4326 tiles

**Arbitrary EPSG Support**:
- System supports any EPSG coordinate system (3857, 4326, 4490, etc.)
- Frontend uses proj4leaflet for non-standard CRS rendering
- Preview map automatically detects proj4 definition availability
- WMTS native mode supports arbitrary EPSG through proj4leaflet

### Performance Optimizations

- **ShardedCache**: 16 shards with independent locks, reduces contention under high concurrency
- **BundlePool**: Reuses file handles, avoids repeated open/close overhead
- Cache keys: `source_level:source_tile_x:source_tile_y:raw` to prevent cross-matrix confusion

## Configuration

Configuration is loaded from `config.yaml` in the current working directory by default. For source checkouts, copy from `config/config.example.yaml`:
```bash
cp config/config.example.yaml config/config.yaml
```

Env overrides via `TILEMAPSERVICE_<SECTION>_<KEY>` or `TILEMAPSERVICE_CONFIG=/path/to/config.yaml`.

**Key sections**:
```yaml
server:
  host: 0.0.0.0
  port: 8000
  debug: false
  graceful_shutdown_timeout: 5

cache:
  enabled: true
  max_size: 1000        # Max cached tiles
  ttl: 3600             # Cache TTL in seconds
  num_shards: 16        # ShardedCache shards for concurrency

bundle_pool:
  enabled: true
  max_size: 50          # Max file handles

cors:
  enabled: true
  allow_origins: ["*"]

defaults:
  spatial_ref:
    wkid: 3857          # Default WKID if no Conf.xml
  tile_origin:
    x: -20037508.342787
    y: 20037508.342787
  tile_size: 256
  infer_bounds: true    # Infer from bundle files if no conf.cdi

sources:
  - name: "my-tiles"
    path: "./data/tiles"
    description: "My tile data"
    # Optional overrides:
    # spatial_ref:
    #   wkid: 4326          # Supports any EPSG code (3857, 4326, 4490, etc.)
    # tile_origin:
    #   x: -180.0
    #   y: 90.0
    # bounds: [-180.0, -90.0, 180.0, 90.0]
```

**Supported directory structures**:
1. Standard `_alllayers`: `path/_alllayers/L00/`, `path/_alllayers/L01/`, ...
2. Direct levels: `path/L00/`, `path/L01/`, ...

**Supported files** (all optional except `.bundle`):
- `Conf.xml` - Tile metadata (WKID, origin, LODs, tile size)
- `conf.cdi` - Data bounds
- `_alllayers/Lxx/*.bundle` - Tile data (V1: requires `.bundlx`, V2: standalone)

Priority: `_alllayers/Lxx/` > `Lxx/`. Missing metadata uses `defaults` config.

## Testing Notes

- `conftest.py` creates mock V1/V2 bundle files for unit tests
- Integration tests require `TILEMAPSERVICE_SAMPLE_DATA` env pointing to real data
- Tests cover: bundle reading, coordinate transforms, tile location, caching, API endpoints, WMTS

## Development Notes

- Use `run_in_threadpool()` for sync Bundle reads and Pillow ops to avoid blocking event loop
- BundlePool requires per-reader locks for thread-safe file operations (see `bundle_pool.py`)
- Graceful shutdown timeout prevents Ctrl+C hangs from long tile requests
- Build uses **onedir mode** to avoid `base_library.zip` errors on Linux
- Frontend includes proj4js 2.9.2 and proj4leaflet 1.0.2 for arbitrary EPSG support
- Preview map uses proj4leaflet for non-standard EPSG codes (e.g., EPSG:4490)
- Empty level directories (without .bundle files) are excluded from available levels
- Out-of-range zoom requests return 404 across all matrix modes (resolution ratio >1.5x threshold)
