"""Redis pub/sub for per-job progress events. Transport only - a missed or
dropped message just means a client's SSE stream was briefly behind the
Mongo snapshot it already got, never a loss of job state.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from redis.asyncio import Redis

_redis: Redis | None = None


def set_redis(client: Redis) -> None:
    """Test hook: swap in a fakeredis client instead of a real one."""
    global _redis
    _redis = client


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("redis not initialized; call connect_redis() first")
    return _redis


async def connect_redis(redis_url: str) -> Redis:
    global _redis
    _redis = Redis.from_url(redis_url, decode_responses=True)
    return _redis


def channel_name(job_id: str) -> str:
    return f"job:{job_id}:events"


async def publish_event(job_id: str, event_type: str, data: dict[str, Any]) -> None:
    redis = get_redis()
    payload = json.dumps({"type": event_type, "data": data})
    await redis.publish(channel_name(job_id), payload)


@asynccontextmanager
async def subscribe(job_id: str) -> AsyncIterator[Any]:
    """Subscribe to a job's channel. The caller MUST subscribe before
    reading the Mongo snapshot (see events.py) so no event published
    between subscribing and snapshotting is lost.
    """
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel_name(job_id))
    # Wait for the subscribe to actually be confirmed before returning:
    # without this, a publish that happens immediately after subscribe()
    # returns can race ahead of the subscription being registered (seen
    # with fakeredis in tests; cheap enough to always do for real redis too).
    await pubsub.get_message(timeout=1.0)
    try:
        yield pubsub
    finally:
        await pubsub.unsubscribe(channel_name(job_id))
        await pubsub.aclose()
