# -*- mode: python ; coding: utf-8 -*-

# CRITICAL FIX for pyproj PROJ database:
# PyInstaller does not auto-collect pyproj's PROJ database files (.db files)
# which are required for coordinate transformations (e.g., EPSG:4326).
# Without these files, pyproj raises:
#   "CRSError: Invalid projection: EPSG:4326: (Internal Proj Error: proj_create: no database context specified)"
# Solution: Use collect_all('pyproj') to bundle data files, binaries, and hiddenimports.

block_cipher = None

from PyInstaller.utils.hooks import collect_all

# Collect pyproj data files (PROJ database)
pyproj_datas, pyproj_binaries, pyproj_hiddenimports = collect_all('pyproj')

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=pyproj_binaries,
    datas=[
        ('config/config.example.yaml', '.'),
        ('src/static', 'static'),
        ('src/tilemapservice', 'tilemapservice'),
    ] + pyproj_datas,
    hiddenimports=[
        # Core Python modules (must be included for PyInstaller)
        'urllib',
        'urllib.request',
        'urllib.parse',
        'urllib.error',
        'zipfile',
        'pathlib',
        'inspect',
        # TileMapService modules
        'tilemapservice.services.sharded_cache',
        'tilemapservice.services.bundle_pool',
        'tilemapservice.services.cache',
        'tilemapservice.services.tile_service',
        'tilemapservice.services.source_manager',
        'tilemapservice.services.tile_locator',
        'tilemapservice.services.image_formatter',
        'tilemapservice.services.capabilities_builder',
        'tilemapservice.services.wmts_service',
        'tilemapservice.readers.bundle_reader',
        'tilemapservice.readers.conf_parser',
        'tilemapservice.readers.cdi_parser',
        'tilemapservice.models.config',
        'tilemapservice.models.source',
        'tilemapservice.models.tile',
        'tilemapservice.models.wmts',
        'tilemapservice.utils.coordinates',
        'tilemapservice.utils.exceptions',
        'tilemapservice.utils.logger',
        'tilemapservice.utils.stats',
        'tilemapservice.api.tiles',
        'tilemapservice.api.metadata',
        'tilemapservice.api.stats',
        'tilemapservice.api.preview',
        'tilemapservice.api.wmts',
        'tilemapservice.api.wmts_exception',
        # Uvicorn and async modules (pre-import for staticx)
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # Async modules (must pre-import for staticx compatibility)
        'anyio',
        'anyio._core',
        'anyio._core._eventloop',
        'anyio.to_thread',
        'anyio.abc',
        'anyio._backends',
        'anyio._backends._asyncio',
        'sniffio',
    ] + pyproj_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'xml.dom',
        'xml.sax',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TileMapService',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TileMapService',
)
