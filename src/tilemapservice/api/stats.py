"""Health and stats routes."""
from fastapi import APIRouter, Request

router = APIRouter()


@router.get(
    "/health",
    tags=["监控"],
    summary="健康检查",
    description="返回服务健康状态、已加载数据源数量和缓存使用情况",
    responses={
        200: {
            "description": "服务健康状态",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "sources_loaded": 2,
                        "cache_size": 150,
                        "cache_max_size": 1000,
                        "cache_enabled": True
                    }
                }
            }
        }
    }
)
async def health_check(request: Request):
    cache_size, cache_max, cache_enabled = request.app.state.cache.capacity()
    return {
        "status": "healthy",
        "sources_loaded": request.app.state.source_manager.count(),
        "cache_size": cache_size,
        "cache_max_size": cache_max,
        "cache_enabled": cache_enabled,
    }


@router.get(
    "/api/stats",
    tags=["监控"],
    summary="获取请求统计",
    description="返回详细的请求统计信息，包括总请求数、成功/失败计数、缓存命中率和平均响应时间",
    responses={
        200: {
            "description": "请求统计信息",
            "content": {
                "application/json": {
                    "example": {
                        "total_requests": 1000,
                        "successful_requests": 980,
                        "failed_requests": 20,
                        "cache_hits": 750,
                        "cache_misses": 250,
                        "cache_hit_rate": 0.75,
                        "avg_response_time_ms": 15.5
                    }
                }
            }
        }
    }
)
async def get_stats(request: Request):
    stats = request.app.state.stats.get_stats()

    # Add cache info
    cache_info = {
        "size": request.app.state.cache.size(),
        "max_size": request.app.state.cache.max_size,
        "enabled": request.app.state.cache.enabled
    }

    # Add sharding info if using ShardedTileCache
    from tilemapservice.services.sharded_cache import ShardedTileCache
    if isinstance(request.app.state.cache, ShardedTileCache):
        cache_info['shards'] = request.app.state.cache.num_shards
        cache_info['shard_size'] = request.app.state.cache.shard_size

    stats['cache'] = cache_info

    # Add bundle_pool stats if enabled
    if hasattr(request.app.state, 'bundle_pool') and request.app.state.bundle_pool:
        stats['bundle_pool'] = request.app.state.bundle_pool.get_stats()

    return stats

