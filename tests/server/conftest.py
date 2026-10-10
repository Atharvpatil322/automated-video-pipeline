"""Server test fixtures: mongomock_motor + fakeredis instead of real Mongo
and Redis, so this suite needs no external services (consistent with the
project-wide "no API keys, no external services to run pytest" rule).
"""

import pytest
from fakeredis import aioredis as fakeredis_aio
from mongomock_motor import AsyncMongoMockClient

from app.server import db as db_module
from app.server import pubsub as pubsub_module
from app.server import queue as queue_module
from app.server.config import Settings, set_settings


class FakeArqPool:
    """Records enqueue_job calls instead of actually queuing - server
    tests either assert against this list directly, or (for lifecycle
    tests) call app.server.pipeline_runner.run_job themselves rather than
    going through a real ARQ worker loop.
    """

    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple]] = []

    async def enqueue_job(self, name: str, *args) -> None:
        self.enqueued.append((name, args))


@pytest.fixture
def fake_db():
    client = AsyncMongoMockClient()
    database = client["test"]
    db_module.set_database(database)
    return database


@pytest.fixture
def fake_redis():
    client = fakeredis_aio.FakeRedis(decode_responses=True)
    pubsub_module.set_redis(client)
    return client


@pytest.fixture
def fake_queue():
    pool = FakeArqPool()
    queue_module.set_pool(pool)
    return pool


@pytest.fixture
def server_settings(tmp_path):
    settings = Settings(
        mongo_url="mongodb://fake",
        mongo_db_name="test",
        redis_url="redis://fake",
        jobs_dir=str(tmp_path),
        offline=True,
        job_timeout_minutes=5,
        cors_origins=["http://localhost:5173"],
        api_token=None,
        max_jobs=None,
    )
    set_settings(settings)
    return settings


@pytest.fixture
async def client(fake_db, fake_redis, fake_queue, server_settings):
    """An httpx.AsyncClient over ASGITransport, run on the *same* event
    loop as the test itself (pytest-asyncio's). The sync `TestClient` runs
    the ASGI app in its own background thread with its own event loop,
    which fakeredis's internals bind to on first use - any test that then
    also `await`s fake_redis directly (on the test's loop) hits "bound to
    a different event loop". ASGITransport avoids a second loop entirely.

    Never used as a context manager / lifespan trigger, so FastAPI's real
    startup (which would try to connect to a real Mongo/Redis and check
    for ffmpeg) never runs - the fakes are already in place via set_*.
    """
    import httpx

    import app.main as main_module

    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
