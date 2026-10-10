"""Regression for a race found via a live docker-compose run: a job's
"Voiceover" stage stayed stuck showing "running" in the UI even after
Assembly and Critic had both completed - impossible in the real pipeline
order, since TTS must finish before assembly starts.

Root cause: ServerCallbacks schedules each stage transition's Mongo write +
Redis publish as an independent fire-and-forget task (`_spawn`), only
reconciled later by `flush()`'s `asyncio.gather`, which runs pending tasks
concurrently with no ordering guarantee between them. For a fast stage
(every offline fake), on_stage_complete's publish could land before
on_stage_start's own publish finished, so the last `stage.tts` event an SSE
client saw was "running" even though "completed" was the true final state.
"""

import asyncio

from app.server.callbacks import ServerCallbacks


async def test_spawn_for_stage_preserves_call_order_even_when_the_first_task_is_slower():
    callbacks = ServerCallbacks("job-race")
    order: list[str] = []

    async def slow_running_write():
        await asyncio.sleep(0.05)  # stands in for a slower Mongo/Redis round trip
        order.append("running")

    async def fast_completed_write():
        order.append("completed")

    # Calls happen in this order (matching on_stage_start then
    # on_stage_complete), but the first one's underlying write is slower -
    # exactly the shape of the race that was observed live.
    callbacks._spawn_for_stage("tts", slow_running_write())
    callbacks._spawn_for_stage("tts", fast_completed_write())
    await callbacks.flush()

    assert order == ["running", "completed"]


async def test_spawn_for_stage_does_not_serialize_unrelated_stages():
    callbacks = ServerCallbacks("job-race-2")
    order: list[str] = []

    async def slow_tts_write():
        await asyncio.sleep(0.05)
        order.append("tts")

    async def fast_visuals_write():
        order.append("visuals")

    callbacks._spawn_for_stage("tts", slow_tts_write())
    callbacks._spawn_for_stage("visuals", fast_visuals_write())
    await callbacks.flush()

    # Different stages aren't chained together, so the faster one is free
    # to finish first.
    assert order == ["visuals", "tts"]


async def test_on_stage_start_then_complete_called_back_to_back_still_ends_completed(
    fake_db, fake_redis
):
    """A looser, closer-to-real-usage check: calling the public callback
    methods exactly as the pipeline does (no await between them, matching
    PipelineCallbacks' sync Protocol) and flushing once, same as
    pipeline_runner.py does after each stage.
    """
    from app.schema.job import JobDocument, JobOptions
    from app.server.db import jobs_collection

    job_id = "job-race-3"
    await jobs_collection().insert_one(
        JobDocument(id=job_id, status="queued", options=JobOptions(topic="t")).model_dump(
            mode="json"
        )
    )

    callbacks = ServerCallbacks(job_id)
    callbacks.on_stage_start("tts")
    callbacks.on_stage_complete("tts", {"word_count": 10})
    await callbacks.flush()

    doc = await jobs_collection().find_one({"id": job_id})
    assert doc["stages"]["tts"]["status"] == "completed"
