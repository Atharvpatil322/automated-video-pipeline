"""Job CRUD + cancel. Mongo is the source of truth (never re-derive job
state from Redis/ARQ); Redis here is only used to enqueue and to stash
per-job keys briefly (see app/server/security.py).
"""

import shutil
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.config.platforms import get_platform
from app.config.registry import get_archetype
from app.schema.job import JobCreateRequest, JobCreateResponse, JobDocument, JobOptions
from app.server.auth import require_api_token
from app.server.config import get_settings
from app.server.db import jobs_collection
from app.server.pubsub import get_redis
from app.server.queue import enqueue_job
from app.server.security import store_job_keys

router = APIRouter(prefix="/api/v1", tags=["jobs"], dependencies=[Depends(require_api_token)])


def _validate_request(request: JobCreateRequest) -> None:
    try:
        get_archetype(request.archetype)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"unknown archetype: {exc}") from exc
    try:
        get_platform(request.platform)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"unknown platform: {exc}") from exc
    if request.score is not None:
        try:
            get_archetype(request.score.archetype)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"score references unknown archetype: {exc}"
            ) from exc


@router.post("/jobs", status_code=201, response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest) -> JobCreateResponse:
    _validate_request(request)

    job_id = str(uuid.uuid4())
    options = JobOptions(
        topic=request.topic,
        archetype=request.archetype,
        platform=request.platform,
        direction=request.direction,
        tts_provider=request.tts_provider,
        image_provider=request.image_provider,
        no_tts=request.no_tts,
        no_visuals=request.no_visuals,
        no_video=request.no_video,
        no_music=request.no_music,
        no_critic=request.no_critic,
        score=request.score,
    )
    document = JobDocument(id=job_id, status="queued", options=options)
    await jobs_collection().insert_one(document.model_dump(mode="json"))

    settings = get_settings()
    ttl_seconds = settings.job_timeout_minutes * 60 + 300
    await store_job_keys(get_redis(), job_id, request.keys, ttl_seconds)

    await enqueue_job(job_id)
    await _prune_old_jobs()

    return JobCreateResponse(
        id=job_id, topic=options.topic, archetype=options.archetype, status="queued"
    )


@router.get("/jobs")
async def list_jobs(limit: int = 50) -> list[dict]:
    cursor = jobs_collection().find().sort("created_at", -1).limit(limit)
    return [_public_view(doc) async for doc in cursor]


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    doc = await jobs_collection().find_one({"id": job_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _public_view(doc)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict:
    doc = await jobs_collection().find_one({"id": job_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="job not found")
    if doc["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=409, detail=f"job already {doc['status']}")

    await jobs_collection().update_one(
        {"id": job_id},
        {"$set": {"cancel_requested": True, "updated_at": datetime.utcnow()}},
    )
    return {
        "id": job_id,
        "cancel_requested": True,
        "message": "cancellation requested; the current stage will finish first",
    }


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str) -> None:
    doc = await jobs_collection().find_one({"id": job_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="job not found")
    if doc["status"] in ("queued", "running"):
        raise HTTPException(status_code=409, detail=f"job is {doc['status']}; cancel it first")

    run_dir = doc.get("run_dir")
    if run_dir:
        shutil.rmtree(run_dir, ignore_errors=True)
    await jobs_collection().delete_one({"id": job_id})


def _public_view(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def _prune_old_jobs() -> None:
    settings = get_settings()
    if not settings.max_jobs:
        return
    terminal = {"completed", "failed", "cancelled"}
    cursor = (
        jobs_collection()
        .find({"status": {"$in": list(terminal)}})
        .sort("created_at", -1)
        .skip(settings.max_jobs)
    )
    async for doc in cursor:
        run_dir = doc.get("run_dir")
        if run_dir:
            shutil.rmtree(run_dir, ignore_errors=True)
        await jobs_collection().delete_one({"id": doc["id"]})
