import uuid

from app.schema.job import ALL_STAGES


def make_payload(**overrides):
    payload = {"topic": "a test topic", "archetype": "infographic", "platform": "youtube"}
    payload.update(overrides)
    return payload


async def test_create_job_rejects_unknown_archetype(client):
    response = await client.post("/api/v1/jobs", json=make_payload(archetype="not-a-real"))
    assert response.status_code == 422


async def test_create_job_rejects_unknown_platform(client):
    response = await client.post("/api/v1/jobs", json=make_payload(platform="not-a-real"))
    assert response.status_code == 422


async def test_create_job_rejects_topic_too_long(client):
    response = await client.post("/api/v1/jobs", json=make_payload(topic="x" * 501))
    assert response.status_code == 422


async def test_create_job_rejects_empty_topic(client):
    response = await client.post("/api/v1/jobs", json=make_payload(topic=""))
    assert response.status_code == 422


async def test_create_job_rejects_direction_too_long(client):
    response = await client.post("/api/v1/jobs", json=make_payload(direction="x" * 10_001))
    assert response.status_code == 422


async def test_create_job_rejects_score_referencing_unknown_archetype(client):
    score = {
        "emotional_arc": "arc",
        "archetype": "not-a-real-archetype",
        "music_mood": "uplifting_pop",
        "scenes": [
            {
                "visual_type": "text_card",
                "visual_prompt": "p",
                "motion": "static",
                "script_line": "line",
                "transition": None,
            }
        ]
        * 3,
    }
    response = await client.post("/api/v1/jobs", json=make_payload(score=score))
    assert response.status_code == 422


async def test_create_job_succeeds_enqueues_and_writes_mongo_doc(client, fake_queue):
    response = await client.post("/api/v1/jobs", json=make_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["topic"] == "a test topic"
    job_id = body["id"]
    uuid.UUID(job_id)  # unguessable id, not a sequential int

    assert len(fake_queue.enqueued) == 1
    assert fake_queue.enqueued[0] == ("run_job_task", (job_id,))

    doc = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert doc["status"] == "queued"
    assert set(doc["stages"].keys()) == set(ALL_STAGES)
    assert all(stage["status"] == "pending" for stage in doc["stages"].values())


async def test_get_job_404_for_unknown_id(client):
    response = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_list_jobs_returns_newest_first(client):
    first = (await client.post("/api/v1/jobs", json=make_payload(topic="first topic"))).json()
    second = (await client.post("/api/v1/jobs", json=make_payload(topic="second topic"))).json()

    jobs = (await client.get("/api/v1/jobs")).json()
    ids = [j["id"] for j in jobs]
    assert ids.index(second["id"]) < ids.index(first["id"])


async def test_cancel_sets_flag_on_queued_job(client):
    job_id = (await client.post("/api/v1/jobs", json=make_payload())).json()["id"]

    response = await client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert response.status_code == 200
    assert response.json()["cancel_requested"] is True

    doc = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert doc["cancel_requested"] is True


async def test_cancel_404_for_unknown_job(client):
    response = await client.post(f"/api/v1/jobs/{uuid.uuid4()}/cancel")
    assert response.status_code == 404


async def test_cancel_409_when_already_terminal(client, fake_db):
    job_id = (await client.post("/api/v1/jobs", json=make_payload())).json()["id"]

    await fake_db.jobs.update_one({"id": job_id}, {"$set": {"status": "completed"}})

    response = await client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert response.status_code == 409


async def test_delete_409_while_queued(client):
    job_id = (await client.post("/api/v1/jobs", json=make_payload())).json()["id"]
    response = await client.delete(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 409


async def test_delete_404_for_unknown_job(client):
    response = await client.delete(f"/api/v1/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_delete_succeeds_when_terminal(client, fake_db):
    job_id = (await client.post("/api/v1/jobs", json=make_payload())).json()["id"]

    await fake_db.jobs.update_one({"id": job_id}, {"$set": {"status": "failed"}})

    response = await client.delete(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 204
    assert (await client.get(f"/api/v1/jobs/{job_id}")).status_code == 404
