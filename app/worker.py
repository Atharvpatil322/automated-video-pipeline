"""ARQ worker: concurrency 1, one render at a time, matching the
reference. Builds providers from the job's own keys (BYOK, read from a
short-lived Redis key and deleted immediately - see app/server/security.py),
runs the pipeline via app/server/pipeline_runner.py, and never retries a
job automatically (`max_tries=1`) since a half-finished render isn't safe
to blindly rerun.
"""

import logging
from datetime import datetime

from app.schema.job import ALL_STAGES, JobOptions
from app.server.config import get_settings
from app.server.db import connect_database, jobs_collection
from app.server.net_utils import host_only
from app.server.pipeline_runner import run_job
from app.server.pubsub import connect_redis
from app.server.redis_settings import build_redis_settings
from app.server.security import pop_job_keys
from app.server.startup_checks import check_render_dependencies

# Nothing else in the process calls logging.basicConfig(); without a
# handler, INFO-level records (the redis/mongo host line below) are
# silently dropped by the logging module's handler-less default - found
# by actually checking `docker compose logs worker` and not seeing the
# line that should have been there.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app.worker")


async def _recover_crashed_jobs() -> None:
    """A job stuck in "running" means the worker that owned it died
    mid-render - never resumed automatically (unsafe), just marked failed
    so the API/UI stop waiting on it forever.
    """
    cursor = jobs_collection().find({"status": "running"})
    async for doc in cursor:
        update = {
            "status": "failed",
            "error": "worker restarted",
            "finished_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        for stage in ALL_STAGES:
            if doc.get("stages", {}).get(stage, {}).get("status") == "running":
                update[f"stages.{stage}.status"] = "error"
                update[f"stages.{stage}.error"] = "worker restarted"
        await jobs_collection().update_one({"id": doc["id"]}, {"$set": update})


async def startup(ctx: dict) -> None:
    check_render_dependencies()
    settings = get_settings()
    logger.info(
        "worker starting: redis=%s mongo=%s",
        host_only(settings.redis_url),
        host_only(settings.mongo_url),
    )
    await connect_database(settings)
    await connect_redis(settings.redis_url)
    await _recover_crashed_jobs()
    ctx["settings"] = settings


async def shutdown(ctx: dict) -> None:
    pass


async def run_job_task(ctx: dict, job_id: str) -> None:
    settings: object = ctx["settings"]
    redis = ctx["redis"]  # arq injects its own redis connection into ctx
    keys = await pop_job_keys(redis, job_id)

    doc = await jobs_collection().find_one({"id": job_id})
    if doc is None:
        return
    options = JobOptions.model_validate(doc["options"])
    await run_job(job_id, options, keys, settings)


class WorkerSettings:
    functions = [run_job_task]
    on_startup = startup
    on_shutdown = shutdown
    # BUG (found in a live docker-compose run): this was `RedisSettings()`,
    # arq's own default, which points at localhost - the worker's own
    # container, not the `redis` compose service - and failed with
    # "redis connection error localhost:6379". Must be built from the
    # configured REDIS_URL, same as app/server/queue.py's enqueue pool.
    redis_settings = build_redis_settings(get_settings().redis_url)
    max_jobs = 1  # concurrency 1, matching the reference
    job_timeout = get_settings().job_timeout_minutes * 60
    max_tries = 1  # never auto-rerun a half-finished render
