"""Route registration."""
from fastapi import APIRouter

from tilemapservice.api import metadata, preview, stats, tiles, wmts

api_router = APIRouter()
api_router.include_router(preview.router)
api_router.include_router(tiles.router)
api_router.include_router(wmts.router)
api_router.include_router(metadata.router)
api_router.include_router(stats.router)

