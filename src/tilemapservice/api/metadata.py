"""Metadata API routes."""
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get(
    "/api/sources",
    tags=["元数据"],
    summary="获取所有数据源列表",
    description="返回系统中所有配置的瓦片数据源的基本信息，包括名称、描述、坐标系、边界和缩放范围",
    responses={
        200: {
            "description": "数据源列表",
            "content": {
                "application/json": {
                    "example": {
                        "sources": [
                            {
                                "name": "world",
                                "description": "世界地图",
                                "srs": "EPSG:3857",
                                "bounds": [-180.0, -85.05112878, 180.0, 85.05112878],
                                "min_zoom": 0,
                                "max_zoom": 18
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def list_sources(request: Request):
    return {
        "sources": [
            {
                "name": source.name,
                "description": source.description,
                "srs": source.srs,
                "bounds": list(source.bounds),
                "min_zoom": source.min_zoom,
                "max_zoom": source.max_zoom,
            }
            for source in request.app.state.source_manager.list_all()
        ]
    }


@router.get(
    "/api/sources/{name}",
    tags=["元数据"],
    summary="获取单个数据源详情",
    description="返回指定数据源的完整配置信息，包括瓦片方案、层级定义和URL模板",
    responses={
        200: {
            "description": "数据源详细信息",
            "content": {
                "application/json": {
                    "example": {
                        "name": "world",
                        "description": "世界地图",
                        "srs": "EPSG:3857",
                        "bounds": [-180.0, -85.05112878, 180.0, 85.05112878],
                        "min_zoom": 0,
                        "max_zoom": 18,
                        "tile_info": {
                            "tile_size": 256,
                            "tile_origin": {"x": -20037508.342787, "y": 20037508.342787},
                            "levels": [{"level": 0, "resolution": 156543.033928}],
                            "matrix": "webmercator"
                        },
                        "tile_url_template": "/tiles/world/{z}/{x}/{y}"
                    }
                }
            }
        },
        404: {
            "description": "数据源不存在",
            "content": {
                "application/json": {
                    "example": {"detail": "数据源 'unknown' 不存在"}
                }
            }
        }
    }
)
async def get_source(request: Request, name: str):
    source = request.app.state.source_manager.get(name)
    if source is None:
        raise HTTPException(status_code=404, detail=f"数据源 '{name}' 不存在")
    return source.to_dict()

