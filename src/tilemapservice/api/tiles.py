"""Tile API routes."""
import asyncio
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from tilemapservice.models.tile import TileRequest
from tilemapservice.utils.exceptions import (
    BundleFormatError,
    ImageFormatError,
    InvalidTileRequestError,
    SourceNotFoundError,
    TileNotFoundError,
    TileReadError,
)

router = APIRouter()


@router.get(
    "/tiles/{source}/tms/{z}/{x}/{y}.{ext}",
    tags=["瓦片服务"],
    summary="获取 TMS 瓦片 (指定格式)",
    description=(
        "使用 TMS (Tile Map Service) 规范获取瓦片，Y 轴原点在底部，支持 PNG/JPEG 格式。\n\n"
        "坐标系说明：\n"
        "- Z: 缩放级别 (0-22)\n"
        "- X: 瓦片列号 (从西向东)\n"
        "- Y: 瓦片行号 (从南向北，与 XYZ 相反)\n\n"
        "支持的格式：`png`, `jpg`, `jpeg`, `auto`"
    ),
    responses={
        200: {
            "description": "成功返回瓦片图片",
            "content": {"image/png": {}, "image/jpeg": {}},
        },
        400: {
            "description": "参数错误或瓦片坐标超出范围",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid format: gif"}
                }
            },
        },
        404: {
            "description": "数据源不存在或瓦片数据缺失",
            "content": {
                "application/json": {
                    "example": {"detail": "Source 'example-tiles' not found"}
                }
            },
        },
    },
)
async def get_tile_tms_ext(
    request: Request,
    source: str,
    z: int,
    x: int,
    y: int,
    ext: str,
    format: str | None = Query(None),
):
    return await _serve_tile(request, source, z, x, y, "EPSG:3857", "webmercator", format or ext, "tms")


@router.get(
    "/tiles/{source}/tms/{z}/{x}/{y}",
    tags=["瓦片服务"],
    summary="获取 TMS 瓦片 (PNG)",
    description=(
        "使用 TMS (Tile Map Service) 规范获取瓦片，Y 轴原点在底部。\n\n"
        "坐标系说明：\n"
        "- Z: 缩放级别 (0-22)\n"
        "- X: 瓦片列号 (从西向东)\n"
        "- Y: 瓦片行号 (从南向北，与 XYZ 相反)\n\n"
        "返回 PNG 格式图片。"
    ),
    responses={
        200: {
            "description": "成功返回瓦片图片",
            "content": {"image/png": {}},
        },
        400: {
            "description": "参数错误或瓦片坐标超出范围",
            "content": {
                "application/json": {
                    "example": {"detail": "Tile coordinates out of range"}
                }
            },
        },
        404: {
            "description": "数据源不存在或瓦片数据缺失",
            "content": {
                "application/json": {
                    "example": {"detail": "Source 'example-tiles' not found"}
                }
            },
        },
    },
)
async def get_tile_tms(
    request: Request,
    source: str,
    z: int,
    x: int,
    y: int,
    format: str = Query("auto"),
):
    return await _serve_tile(request, source, z, x, y, "EPSG:3857", "webmercator", format, "tms")


@router.get(
    "/tiles/{source}/crs/epsg:{epsg}/{z}/{x}/{y}.{ext}",
    tags=["瓦片服务"],
    summary="获取显式 CRS 瓦片 (指定格式)",
    description=(
        "使用显式坐标参考系统 (CRS) 获取瓦片，支持 PNG/JPEG 格式。\n\n"
        "参数说明：\n"
        "- `epsg`: EPSG 代码 (如 3857, 4326, 4490)\n"
        "- `matrix`: 瓦片矩阵类型\n"
        "  - `source`: 使用数据源原生坐标系统 (默认)\n"
        "  - `webmercator`: Web Mercator (EPSG:3857)\n"
        "  - `geographic`: 地理坐标系 (EPSG:4326)\n\n"
        "支持的格式：`png`, `jpg`, `jpeg`, `auto`"
    ),
    responses={
        200: {
            "description": "成功返回瓦片图片",
            "content": {"image/png": {}, "image/jpeg": {}},
        },
        400: {
            "description": "参数错误、CRS 不匹配或瓦片坐标超出范围",
            "content": {
                "application/json": {
                    "example": {"detail": "CRS mismatch: requested EPSG:4326, source has EPSG:3857"}
                }
            },
        },
        404: {
            "description": "数据源不存在或瓦片数据缺失",
            "content": {
                "application/json": {
                    "example": {"detail": "Source 'example-tiles' not found"}
                }
            },
        },
    },
)
async def get_tile_epsg_ext(
    request: Request,
    source: str,
    epsg: int,
    z: int,
    x: int,
    y: int,
    ext: str,
    matrix: str = Query("source"),
    format: str | None = Query(None),
):
    return await _serve_tile(request, source, z, x, y, f"EPSG:{epsg}", matrix, format or ext, "xyz")


@router.get(
    "/tiles/{source}/crs/epsg:{epsg}/{z}/{x}/{y}",
    tags=["瓦片服务"],
    summary="获取显式 CRS 瓦片 (PNG)",
    description=(
        "使用显式坐标参考系统 (CRS) 获取瓦片。\n\n"
        "参数说明：\n"
        "- `epsg`: EPSG 代码 (如 3857, 4326, 4490)\n"
        "- `matrix`: 瓦片矩阵类型\n"
        "  - `source`: 使用数据源原生坐标系统 (默认)\n"
        "  - `webmercator`: Web Mercator (EPSG:3857)\n"
        "  - `geographic`: 地理坐标系 (EPSG:4326)\n\n"
        "返回 PNG 格式图片。"
    ),
    responses={
        200: {
            "description": "成功返回瓦片图片",
            "content": {"image/png": {}},
        },
        400: {
            "description": "参数错误、CRS 不匹配或瓦片坐标超出范围",
            "content": {
                "application/json": {
                    "example": {"detail": "CRS mismatch: requested EPSG:4326, source has EPSG:3857"}
                }
            },
        },
        404: {
            "description": "数据源不存在或瓦片数据缺失",
            "content": {
                "application/json": {
                    "example": {"detail": "Source 'example-tiles' not found"}
                }
            },
        },
    },
)
async def get_tile_epsg(
    request: Request,
    source: str,
    epsg: int,
    z: int,
    x: int,
    y: int,
    matrix: str = Query("source"),
    format: str = Query("auto"),
):
    return await _serve_tile(request, source, z, x, y, f"EPSG:{epsg}", matrix, format, "xyz")


@router.get(
    "/tiles/{source}/{z}/{x}/{y}.{ext}",
    tags=["瓦片服务"],
    summary="获取 XYZ 瓦片 (指定格式)",
    description=(
        "使用 Web Mercator (EPSG:3857) 坐标系获取瓦片，支持 PNG/JPEG 格式。\n\n"
        "坐标系说明：\n"
        "- Z: 缩放级别 (0-22)\n"
        "- X: 瓦片列号 (从西向东)\n"
        "- Y: 瓦片行号 (从北向南)\n\n"
        "支持的格式：`png`, `jpg`, `jpeg`, `auto`"
    ),
    responses={
        200: {
            "description": "成功返回瓦片图片",
            "content": {"image/png": {}, "image/jpeg": {}},
        },
        400: {
            "description": "参数错误或瓦片坐标超出范围",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid format: gif"}
                }
            },
        },
        404: {
            "description": "数据源不存在或瓦片数据缺失",
            "content": {
                "application/json": {
                    "example": {"detail": "Source 'example-tiles' not found"}
                }
            },
        },
    },
)
async def get_tile_xyz_ext(
    request: Request,
    source: str,
    z: int,
    x: int,
    y: int,
    ext: str,
    format: str | None = Query(None),
):
    return await _serve_tile(request, source, z, x, y, "EPSG:3857", "webmercator", format or ext, "xyz")


@router.get(
    "/tiles/{source}/{z}/{x}/{y}",
    tags=["瓦片服务"],
    summary="获取 XYZ 瓦片 (PNG)",
    description=(
        "使用 Web Mercator (EPSG:3857) 坐标系获取瓦片。\n\n"
        "坐标系说明：\n"
        "- Z: 缩放级别 (0-22)\n"
        "- X: 瓦片列号 (从西向东)\n"
        "- Y: 瓦片行号 (从北向南)\n\n"
        "返回 PNG 格式图片。"
    ),
    responses={
        200: {
            "description": "成功返回瓦片图片",
            "content": {"image/png": {}},
        },
        400: {
            "description": "参数错误或瓦片坐标超出范围",
            "content": {
                "application/json": {
                    "example": {"detail": "Tile coordinates out of range"}
                }
            },
        },
        404: {
            "description": "数据源不存在或瓦片数据缺失",
            "content": {
                "application/json": {
                    "example": {"detail": "Source 'example-tiles' not found"}
                }
            },
        },
    },
)
async def get_tile_xyz(
    request: Request,
    source: str,
    z: int,
    x: int,
    y: int,
    format: str = Query("auto"),
):
    return await _serve_tile(request, source, z, x, y, "EPSG:3857", "webmercator", format, "xyz")


async def _serve_tile(
    request: Request,
    source: str,
    z: int,
    x: int,
    y: int,
    srs: str,
    matrix: str,
    output_format: str,
    service_type: str,
):
    tile_request = TileRequest(
        source_name=source,
        z=z,
        x=x,
        y=y,
        srs=srs,
        matrix=matrix,
        output_format=output_format,
        service_type=service_type
    )
    stats = request.app.state.stats
    try:
        tile_response = await asyncio.to_thread(request.app.state.tile_service.get_tile, tile_request)
    except InvalidTileRequestError as exc:
        stats.record_request(False, source)
        raise HTTPException(status_code=400, detail={"error": exc.__class__.__name__, "message": exc.message, "context": exc.context})
    except (SourceNotFoundError, TileNotFoundError) as exc:
        stats.record_request(False, source)
        raise HTTPException(status_code=404, detail={"error": exc.__class__.__name__, "message": exc.message, "context": exc.context})
    except (BundleFormatError, TileReadError, ImageFormatError) as exc:
        stats.record_request(False, source)
        raise HTTPException(status_code=500, detail={"error": exc.__class__.__name__, "message": exc.message, "context": exc.context})

    stats.record_request(True, source)
    return Response(
        content=tile_response.data,
        media_type=tile_response.content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Tile-Source": source,
            "X-Source-Level": str(tile_response.source_level),
        },
    )
