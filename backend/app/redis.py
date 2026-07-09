import asyncio
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool, MaxConnectionsError

from app.config import settings
from app.core.logging import logger


class _BlockingPool(ConnectionPool):
    async def get_connection(self, command_name=None, *keys, **options):
        while True:
            try:
                return await super().get_connection(command_name, *keys, **options)
            except MaxConnectionsError:
                await asyncio.sleep(0.05)


_pool: _BlockingPool | None = None
_pool_lock = asyncio.Lock()


async def get_redis() -> redis.Redis | None:
    if not settings.REDIS_URL:
        return None
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = _BlockingPool.from_url(
                    settings.REDIS_URL,
                    max_connections=8,
                    decode_responses=True,
                    socket_connect_timeout=10,
                    socket_timeout=30,
                    retry_on_timeout=True,
                )
    return redis.Redis(connection_pool=_pool)


async def close_redis():
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None
