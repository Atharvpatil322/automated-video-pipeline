"""Full job lifecycle, run directly against app.server.pipeline_runner.run_job
(not through a real ARQ worker loop) - offline mode, no_tts=True so it never
touches ffmpeg, keeping this test independent of the render toolchain like
every other non-render test in this suite.
"""

import shutil

import pytest

from app.schema.job import JobDocument, JobOptions
from app.server.db import jobs_collection
from app.server.pipeline_runner import run_job

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


async def _insert_job(job_id: str, options: JobOptions) -> None:
    document = JobDocument(id=job_id, status="queued", options=options)
    await jobs_collection().insert_one(document.model_dump(mode="json"))


async def test_full_lifecycle_reaches_completed(fake_db, fake_redis, server_settings):
    job_id = "job-1"
    options = JobOptions(topic="a lifecycle topic", archetype="infographic", no_tts=True)
    await _insert_job(job_id, options)

    await run_job(job_id, options, keys={}, settings=server_settings)

    doc = await jobs_collection().find_one({"id": job_id})
    assert doc["status"] == "completed"
    assert doc["stages"]["research"]["status"] == "completed"
    assert doc["stages"]["director"]["status"] == "completed"
    assert doc["stages"]["tts"]["status"] == "skipped"
    assert doc["stages"]["tts"]["reason"] == "no_tts"
    assert doc["stages"]["visuals"]["status"] == "skipped"
    assert doc["stages"]["assembly"]["status"] == "skipped"
    assert doc["score"] is not None
    assert doc["cost_estimate"] is not None
    assert doc["cost_actual"] is not None
    assert doc["finished_at"] is not None


async def test_failed_stage_marks_job_failed(fake_db, fake_redis, server_settings, monkeypatch):
    job_id = "job-2"
    options = JobOptions(topic="a failing topic", archetype="infographic", no_tts=True)
    await _insert_job(job_id, options)

    from app.agents import research as research_agent

    async def boom(topic, llm):
        raise RuntimeError("research exploded")

    monkeypatch.setattr(research_agent, "research", boom)
    # pipeline_runner imported `research` by name, so patch it there too
    import app.server.pipeline_runner as runner_module

    monkeypatch.setattr(runner_module, "research", boom)

    try:
        await run_job(job_id, options, keys={}, settings=server_settings)
    except RuntimeError:
        pass

    doc = await jobs_collection().find_one({"id": job_id})
    assert doc["status"] == "failed"
    assert "research exploded" in doc["error"]


async def test_cancel_requested_before_tts_skips_remaining_stages(
    fake_db, fake_redis, server_settings
):
    job_id = "job-3"
    options = JobOptions(topic="a cancel topic", archetype="infographic")
    await _insert_job(job_id, options)

    # Flip cancel_requested the moment the director stage finishes, by
    # racing a real job run against a tiny watcher - simpler and more
    # realistic than monkeypatching: just set it before calling run_job,
    # simulating a cancel that landed after job creation but before the
    # worker picked it up (still "cooperative, between stages").
    await jobs_collection().update_one({"id": job_id}, {"$set": {"cancel_requested": True}})

    await run_job(job_id, options, keys={}, settings=server_settings)

    doc = await jobs_collection().find_one({"id": job_id})
    assert doc["status"] == "cancelled"
    assert doc["stages"]["tts"]["status"] == "skipped"
    assert doc["stages"]["tts"]["reason"] == "cancelled"
    assert doc["stages"]["visuals"]["status"] == "skipped"
    assert doc["stages"]["assembly"]["status"] == "skipped"
    # director still ran to completion - cancel is cooperative, not preemptive
    assert doc["stages"]["director"]["status"] == "completed"


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg not found on PATH")
async def test_offline_job_with_tts_and_visuals_is_priced_at_zero(
    fake_db, fake_redis, server_settings
):
    """Regression for a bug found in a live docker-compose run: offline
    mode swapped the actual provider *implementations* for TTS/images but
    kept pricing cost_estimate/cost_actual against whatever
    tts_provider/image_provider the request asked for (elevenlabs/openai
    by default) - an OFFLINE job showed a non-zero cost for calls it never
    actually made. This needs TTS/visuals to actually run (not no_tts=True
    like the other lifecycle tests here) to exercise that pricing path, so
    it needs real ffmpeg (the offline fakes render through it) and skips
    without it, same as the render/assembly tests elsewhere in this repo.
    """
    job_id = "job-4"
    options = JobOptions(
        topic="a priced topic",
        archetype="infographic",
        tts_provider="elevenlabs",  # deliberately NOT "offline" - the request
        image_provider="openai",  # default; offline mode must override both
        no_video=True,
        no_critic=True,
    )
    await _insert_job(job_id, options)

    await run_job(job_id, options, keys={}, settings=server_settings)

    doc = await jobs_collection().find_one({"id": job_id})
    assert doc["status"] == "completed"
    assert doc["cost_estimate"]["breakdown"]["tts"] == 0.0
    assert doc["cost_estimate"]["breakdown"]["images"] == 0.0
    assert doc["cost_actual"]["breakdown"]["tts"] == 0.0
    assert doc["cost_actual"]["breakdown"]["images"] == 0.0
