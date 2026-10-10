from app.schema.job import JobDocument, JobOptions, StageRecord
from app.server.db import jobs_collection
from app.worker import _recover_crashed_jobs


async def test_recover_marks_running_job_failed_with_worker_restarted_reason(
    fake_db, server_settings
):
    doc = JobDocument(
        id="stuck-job",
        status="running",
        options=JobOptions(topic="t"),
        stages={
            "research": StageRecord(status="completed"),
            "director": StageRecord(status="completed"),
            "tts": StageRecord(status="running"),
            "visuals": StageRecord(status="pending"),
            "assembly": StageRecord(status="pending"),
            "critic": StageRecord(status="pending"),
        },
    )
    await jobs_collection().insert_one(doc.model_dump(mode="json"))

    await _recover_crashed_jobs()

    recovered = await jobs_collection().find_one({"id": "stuck-job"})
    assert recovered["status"] == "failed"
    assert recovered["error"] == "worker restarted"
    assert recovered["stages"]["tts"]["status"] == "error"
    assert recovered["stages"]["tts"]["error"] == "worker restarted"
    # stages that weren't running are left alone
    assert recovered["stages"]["research"]["status"] == "completed"
    assert recovered["stages"]["visuals"]["status"] == "pending"


async def test_recover_leaves_completed_and_queued_jobs_alone(fake_db, server_settings):
    completed = JobDocument(id="done-job", status="completed", options=JobOptions(topic="t"))
    queued = JobDocument(id="queued-job", status="queued", options=JobOptions(topic="t"))
    await jobs_collection().insert_one(completed.model_dump(mode="json"))
    await jobs_collection().insert_one(queued.model_dump(mode="json"))

    await _recover_crashed_jobs()

    assert (await jobs_collection().find_one({"id": "done-job"}))["status"] == "completed"
    assert (await jobs_collection().find_one({"id": "queued-job"}))["status"] == "queued"


async def test_recover_with_no_running_jobs_does_nothing(fake_db, server_settings):
    await _recover_crashed_jobs()  # should not raise with an empty collection
