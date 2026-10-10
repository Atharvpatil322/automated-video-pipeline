"""Per-job API keys must never land in Mongo (the durable store) or sit in
Redis past the worker reading them once, and must never appear in log
output. This scans all three after a full flow, rather than just asserting
against one code path, since a leak could show up almost anywhere.
"""

import json
import logging

from app.server.db import jobs_collection
from app.server.security import (
    SecretRedactingFilter,
    pop_job_keys,
    redact_text,
    register_secret,
    store_job_keys,
)

SECRET_VALUE = "sk-super-secret-key-value-12345"


async def test_store_and_pop_job_keys_roundtrip(fake_redis, server_settings):
    await store_job_keys(fake_redis, "job-1", {"groq": SECRET_VALUE}, ttl_seconds=60)

    popped = await pop_job_keys(fake_redis, "job-1")
    assert popped == {"groq": SECRET_VALUE}

    # read-and-delete: a second pop finds nothing left
    assert await pop_job_keys(fake_redis, "job-1") == {}


async def test_stored_key_has_a_ttl(fake_redis, server_settings):
    await store_job_keys(fake_redis, "job-2", {"groq": SECRET_VALUE}, ttl_seconds=60)
    ttl = await fake_redis.ttl("job:job-2:keys")
    assert 0 < ttl <= 60


async def test_create_job_keys_never_appear_in_the_mongo_document(client, fake_db):
    response = await client.post(
        "/api/v1/jobs",
        json={
            "topic": "t",
            "archetype": "infographic",
            "platform": "youtube",
            "keys": {"groq": SECRET_VALUE},
        },
    )
    job_id = response.json()["id"]

    doc = await jobs_collection().find_one({"id": job_id})
    doc.pop("_id", None)
    assert SECRET_VALUE not in json.dumps(doc, default=str)


async def test_create_job_keys_are_removed_from_redis_once_the_worker_reads_them(
    client, fake_redis
):
    response = await client.post(
        "/api/v1/jobs",
        json={
            "topic": "t",
            "archetype": "infographic",
            "platform": "youtube",
            "keys": {"groq": SECRET_VALUE},
        },
    )
    job_id = response.json()["id"]

    # simulate the worker's first action on this job
    keys = await pop_job_keys(fake_redis, job_id)
    assert keys == {"groq": SECRET_VALUE}

    all_keys = await fake_redis.keys("*")
    all_values = []
    for key in all_keys:
        value = await fake_redis.get(key)
        if value is not None:
            all_values.append(value)
    assert all(SECRET_VALUE not in v for v in all_values)


def test_redact_text_scrubs_a_registered_secret():
    register_secret(SECRET_VALUE)
    redacted = redact_text(f"using key {SECRET_VALUE} for this call")
    assert redacted == "using key ***REDACTED*** for this call"


def test_logging_filter_scrubs_secret_from_log_records(caplog):
    register_secret(SECRET_VALUE)
    logger = logging.getLogger("test.secrets")
    logger.addFilter(SecretRedactingFilter())

    with caplog.at_level(logging.INFO, logger="test.secrets"):
        logger.info("calling provider with key=%s", SECRET_VALUE)

    for record in caplog.records:
        assert SECRET_VALUE not in record.getMessage()


async def test_full_flow_secret_scan_across_mongo_redis_and_logs(
    client, fake_db, fake_redis, caplog
):
    """The scan the brief asked for: run a job's key through create -> pop
    (worker read), then check the secret string is absent from the Mongo
    document, every remaining Redis key's value, and anything logged.
    """
    logger = logging.getLogger("test.full_flow")
    logger.addFilter(SecretRedactingFilter())

    response = await client.post(
        "/api/v1/jobs",
        json={
            "topic": "t",
            "archetype": "infographic",
            "platform": "youtube",
            "keys": {"groq": SECRET_VALUE},
        },
    )
    job_id = response.json()["id"]

    with caplog.at_level(logging.INFO):
        keys = await pop_job_keys(fake_redis, job_id)
        logger.info("worker picked up job %s with keys %s", job_id, keys)

    # 1. Mongo
    doc = await jobs_collection().find_one({"id": job_id})
    doc.pop("_id", None)
    assert SECRET_VALUE not in json.dumps(doc, default=str)

    # 2. Redis - nothing left referencing the secret
    for key in await fake_redis.keys("*"):
        value = await fake_redis.get(key)
        if value is not None:
            assert SECRET_VALUE not in value

    # 3. Logs
    for record in caplog.records:
        assert SECRET_VALUE not in record.getMessage()
