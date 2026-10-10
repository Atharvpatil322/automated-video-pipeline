"""SSE tests drive app.server.routes.events._event_stream directly (the
actual generator the HTTP route wraps in EventSourceResponse) rather than
going through TestClient's streaming transport, which is more deterministic
for interleaving "publish while the generator is mid-flight" than a real
threaded HTTP stream would be - the logic under test (subscribe-before-
snapshot ordering, terminal-event handling) lives entirely in that
generator either way.
"""

import json
import uuid

import pytest

import app.server.routes.events as events_module
from app.schema.job import JobDocument, JobOptions
from app.server.db import jobs_collection
from app.server.pubsub import publish_event
from app.server.routes.events import _event_stream


class FakeRequest:
    def __init__(self) -> None:
        self.disconnected = False

    async def is_disconnected(self) -> bool:
        return self.disconnected


async def _insert(job_id: str, status: str = "queued") -> None:
    doc = JobDocument(id=job_id, status=status, options=JobOptions(topic="t"))
    await jobs_collection().insert_one(doc.model_dump(mode="json"))


async def test_snapshot_sent_first_then_live_events(fake_db, fake_redis, server_settings):
    job_id = "job-snap"
    await _insert(job_id)

    gen = _event_stream(job_id, FakeRequest())

    first = await gen.__anext__()
    assert first["event"] == "job.snapshot"
    assert json.loads(first["data"])["status"] == "queued"

    await publish_event(job_id, "stage.tts", {"status": "running"})
    second = await gen.__anext__()
    assert second["event"] == "stage.tts"
    assert json.loads(second["data"]) == {"status": "running"}

    await publish_event(job_id, "job.completed", {"status": "completed"})
    third = await gen.__anext__()
    assert third["event"] == "job.completed"

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


async def test_subscribe_happens_before_snapshot_so_a_racing_publish_is_not_lost(
    fake_db, fake_redis, server_settings, monkeypatch
):
    job_id = "job-race"
    await _insert(job_id)

    # `jobs_collection()` returns a fresh wrapper object on every call (not
    # a cached singleton), so the race has to be simulated by patching the
    # *function* events.py calls, not an instance obtained once here.
    real_jobs_collection = events_module.jobs_collection

    class RacingCollection:
        def __getattr__(self, name):
            return getattr(real_jobs_collection(), name)

        async def find_one(self, *args, **kwargs):
            # Simulates a worker publishing a progress event at the exact
            # moment the API reads the Mongo snapshot. This only survives
            # because _event_stream subscribes before calling find_one.
            await publish_event(job_id, "stage.director", {"status": "running"})
            return await real_jobs_collection().find_one(*args, **kwargs)

    monkeypatch.setattr(events_module, "jobs_collection", lambda: RacingCollection())

    gen = _event_stream(job_id, FakeRequest())

    first = await gen.__anext__()
    assert first["event"] == "job.snapshot"

    second = await gen.__anext__()
    assert second["event"] == "stage.director"


async def test_reconnect_after_job_already_terminal_sends_snapshot_then_closes(
    fake_db, fake_redis, server_settings
):
    job_id = "job-done"
    await _insert(job_id, status="completed")

    gen = _event_stream(job_id, FakeRequest())

    first = await gen.__anext__()
    assert first["event"] == "job.snapshot"

    second = await gen.__anext__()
    assert second["event"] == "job.completed"

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


async def test_unknown_job_yields_error_event(fake_db, fake_redis, server_settings):
    gen = _event_stream("no-such-job", FakeRequest())

    first = await gen.__anext__()
    assert first["event"] == "error"

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


async def test_events_route_404_for_unknown_job_before_streaming(client):
    response = await client.get(f"/api/v1/jobs/{uuid.uuid4()}/events")
    assert response.status_code == 404


async def test_events_route_200_for_a_terminal_job_over_real_http(client, fake_db):
    # Exercises the real route/ASGI wiring (status, content-type, body)
    # end to end - but only for an already-terminal job, whose stream
    # ends itself almost immediately (snapshot + terminal event, then the
    # generator returns). A still-running job's stream never ends on its
    # own, and draining a genuinely long-lived SSE body over httpx's
    # in-process ASGITransport (no real socket, so no real client-
    # disconnect signal) turned out to hang rather than complete; the
    # snapshot/race/reconnect logic itself is already covered thoroughly
    # by the direct _event_stream() generator tests above.
    created = await client.post(
        "/api/v1/jobs", json={"topic": "t", "archetype": "infographic", "platform": "youtube"}
    )
    job_id = created.json()["id"]
    await fake_db.jobs.update_one({"id": job_id}, {"$set": {"status": "completed"}})

    async with client.stream("GET", f"/api/v1/jobs/{job_id}/events") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = b""
        async for chunk in response.aiter_bytes():
            body += chunk
    assert b"job.snapshot" in body
    assert b"job.completed" in body
