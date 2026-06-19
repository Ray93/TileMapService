"""WMTS API routes supporting KVP and RESTful styles."""
import asyncio
from fastapi import APIRouter, Request, Query, Path
from fastapi.responses import Response, RedirectResponse

from tilemapservice.models.wmts import WmtsTileRequest
from tilemapservice.services.wmts_service import WmtsService
from tilemapservice.api.wmts_exception import ServiceExceptionReport
from tilemapservice.utils.exceptions import (
    InvalidTileRequestError,
    SourceNotFoundError,
    TileNotFoundError,
    BundleFormatError,
    TileReadError,
    ImageFormatError,
)

router = APIRouter()


@router.get(
    "/wmts",
    tags=["WMTS"],
    summary="WMTS GetCapabilities / GetTile",
    description=(
        "OGC WMTS 1.0.0 标准端点。支持以下操作：\n\n"
        "- GetCapabilities: 获取服务能力描述 (XML)\n"
        "- GetTile: 获取指定瓦片\n\n"
        "通过 REQUEST 参数指定操作类型。如果只提供 SERVICE=WMTS，默认返回 GetCapabilities。"
    ),
    responses={
        200: {
            "description": "成功返回 Capabilities XML 或瓦片图片",
        },
        400: {
            "description": "请求参数错误",
            "content": {
                "application/xml": {
                    "example": '<?xml version="1.0"?><ServiceException>Invalid REQUEST parameter</ServiceException>'
                }
            },
        },
    },
)
async def wmts_root(
    request: Request,
    service: str | None = Query(None),
    request_param: str | None = Query(None, alias="request"),
    version: str | None = Query(None),
    layer: str | None = Query(None),
    style: str | None = Query(None),
    tilematrixset: str | None = Query(None),
    tilematrix: int | None = Query(None),
    tilerow: int | None = Query(None),
    tilecol: int | None = Query(None),
    format: str | None = Query(None),
):
    """Handle WMTS KVP requests.

    If no parameters provided, redirects to GetCapabilities.
    """
    # Default to GetCapabilities if service=WMTS without request
    if service == "WMTS" and request_param is None:
        request_param = "GetCapabilities"

    if service != "WMTS":
        return _error_response("InvalidParameterValue", f"Invalid service: {service}")

    if request_param == "GetCapabilities":
        return await get_capabilities(request)
    elif request_param == "GetTile":
        return await get_tile_kvp(
            request, layer, style, tilematrixset, tilematrix, tilerow, tilecol, format
        )
    else:
        return _error_response(
            "OperationNotSupported",
            f"Unknown request: {request_param}",
        )


async def get_capabilities(request: Request) -> Response:
    """Return WMTS GetCapabilities XML response."""
    capabilities = getattr(request.app.state, "wmts_capabilities", None)
    if capabilities is None:
        return _error_response(
            "NoApplicableCode",
            "WMTS capabilities not initialized",
        )
    return Response(
        content=capabilities,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


async def get_tile_kvp(
    request: Request,
    layer: str | None,
    style: str | None,
    tilematrixset: str | None,
    tilematrix: int | None,
    tilerow: int | None,
    tilecol: int | None,
    format: str | None,
) -> Response:
    """Handle KVP GetTile request."""
    # Validate required parameters
    if layer is None:
        return _error_response("MissingParameterValue", "Missing required parameter: layer")
    if tilematrixset is None:
        return _error_response("MissingParameterValue", "Missing required parameter: tilematrixset")
    if tilematrix is None:
        return _error_response("MissingParameterValue", "Missing required parameter: tilematrix")
    if tilerow is None:
        return _error_response("MissingParameterValue", "Missing required parameter: tilerow")
    if tilecol is None:
        return _error_response("MissingParameterValue", "Missing required parameter: tilecol")

    wmts_request = WmtsTileRequest(
        layer=layer,
        style=style or "default",
        tilematrixset=tilematrixset,
        tilematrix=tilematrix,
        tilerow=tilerow,
        tilecol=tilecol,
        format=format or "image/png",
    )
    return await _serve_wmts_tile(request, wmts_request)


@router.get(
    "/wmts/{layer}/{style}/{tilematrixset}/{tilematrix}/{tilerow}/{tilecol}.{format_ext}"
)
async def get_tile_restful_with_format(
    request: Request,
    layer: str = Path(...),
    style: str = Path(...),
    tilematrixset: str = Path(...),
    tilematrix: int = Path(...),
    tilerow: int = Path(...),
    tilecol: int = Path(...),
    format_ext: str = Path(...),
):
    """Handle RESTful GetTile request with format extension."""
    # Map extension to MIME type
    format_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }
    format_mime = format_map.get(format_ext.lower(), f"image/{format_ext}")

    wmts_request = WmtsTileRequest(
        layer=layer,
        style=style,
        tilematrixset=tilematrixset,
        tilematrix=tilematrix,
        tilerow=tilerow,
        tilecol=tilecol,
        format=format_mime,
    )
    return await _serve_wmts_tile(request, wmts_request)


@router.get(
    "/wmts/{layer}/{style}/{tilematrixset}/{tilematrix}/{tilerow}/{tilecol}",
    tags=["WMTS"],
    summary="WMTS RESTful GetTile",
    description="RESTful 风格的 WMTS GetTile 请求。直接通过 URL 路径指定瓦片坐标。",
    responses={
        200: {"description": "成功返回瓦片图片"},
        400: {"description": "参数错误"},
        404: {"description": "数据源或瓦片不存在"},
    },
)
async def get_tile_restful(
    request: Request,
    layer: str = Path(...),
    style: str = Path(...),
    tilematrixset: str = Path(...),
    tilematrix: int = Path(...),
    tilerow: int = Path(...),
    tilecol: int = Path(...),
    format: str = Query("image/png"),
):
    """Handle RESTful GetTile request without format extension."""
    wmts_request = WmtsTileRequest(
        layer=layer,
        style=style,
        tilematrixset=tilematrixset,
        tilematrix=tilematrix,
        tilerow=tilerow,
        tilecol=tilecol,
        format=format,
    )
    return await _serve_wmts_tile(request, wmts_request)


async def _serve_wmts_tile(
    request: Request, wmts_request: WmtsTileRequest
) -> Response:
    """Serve a tile for WMTS request."""
    tile_service = request.app.state.tile_service
    source_manager = request.app.state.source_manager
    wmts_service = WmtsService(tile_service, source_manager)
    stats = request.app.state.stats

    try:
        tile_response = await asyncio.to_thread(wmts_service.get_tile, wmts_request)
    except InvalidTileRequestError as exc:
        stats.record_request(False, wmts_request.layer)
        return _error_response("InvalidParameterValue", exc.message)
    except SourceNotFoundError as exc:
        stats.record_request(False, wmts_request.layer)
        return _error_response("LayerNotDefined", exc.message)
    except TileNotFoundError as exc:
        stats.record_request(False, wmts_request.layer)
        return _error_response("TileNotFound", exc.message)
    except (BundleFormatError, TileReadError, ImageFormatError) as exc:
        stats.record_request(False, wmts_request.layer)
        return _error_response("NoApplicableCode", exc.message)

    stats.record_request(True, wmts_request.layer)
    return Response(
        content=tile_response.data,
        media_type=tile_response.content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Tile-Source": wmts_request.layer,
            "X-Source-Level": str(tile_response.source_level),
        },
    )


def _error_response(code: str, message: str) -> Response:
    """Create a ServiceException XML response."""
    report = ServiceExceptionReport(code, message)
    return Response(
        content=report.to_xml(),
        media_type="application/xml",
        status_code=400,
    )


def _get_service_url(request: Request) -> str:
    """Extract base URL from request for capabilities generation."""
    return str(request.url).rsplit("/wmts", 1)[0] + "/wmts"