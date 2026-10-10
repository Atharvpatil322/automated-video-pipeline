"""Mongo connection + indexes. A single module-level holder so routes,
the worker, and tests can all get/replace the same database handle
without needing a dependency-injection framework.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.server.config import Settings

_db: AsyncIOMotorDatabase | None = None


def set_database(db: AsyncIOMotorDatabase) -> None:
    """Test hook: swap in a mongomock_motor database instead of a real one."""
    global _db
    _db = db


def get_database() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("database not initialized; call connect_database() first")
    return _db


async def connect_database(settings: Settings) -> AsyncIOMotorDatabase:
    global _db
    client = AsyncIOMotorClient(settings.mongo_url)
    _db = client[settings.mongo_db_name]
    await _db.jobs.create_index([("created_at", -1)])
    await _db.jobs.create_index([("status", 1)])
    return _db


def jobs_collection():
    return get_database().jobs
