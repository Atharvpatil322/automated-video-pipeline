"""ARQ job enqueueing from the API process. Kept separate from pubsub.py's
raw redis client since arq needs its own connection pool type.
"""

from arq import ArqRedis
from arq.connections import create_pool

from app.server.redis_settings import build_redis_settings

_pool: ArqRedis | None = None


def set_pool(pool: ArqRedis) -> None:
    """Test hook: swap in a pool built against fakeredis."""
    global _pool
    _pool = pool


def get_pool() -> ArqRedis:
    if _pool is None:
        raise RuntimeError("arq pool not initialized; call connect_queue() first")
    return _pool


async def connect_queue(redis_url: str) -> ArqRedis:
    global _pool
    _pool = await create_pool(build_redis_settings(redis_url))
    return _pool


async def enqueue_job(job_id: str) -> None:
    await get_pool().enqueue_job("run_job_task", job_id)
