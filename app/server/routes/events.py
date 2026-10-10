"""SSE: subscribe to the job's Redis channel BEFORE reading the Mongo
snapshot, then send `job.snapshot`, then forward live events. Subscribing
first means any event published between "subscribe" and "snapshot read"
is still captured (buffered by the pubsub object) rather than lost -
that ordering is the whole point of this file.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.server.auth import require_api_token
from app.server.db import jobs_collection
from app.server.pubsub import subscribe

router = APIRouter(prefix="/api/v1", tags=["events"], dependencies=[Depends(require_api_token)])

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
KEEPALIVE_TIMEOUT_S = 15.0


def _public_view(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def _event_stream(job_id: str, request: Request):
    async with subscribe(job_id) as pubsub:
        doc = await jobs_collection().find_one({"id": job_id})
        if doc is None:
            yield {"event": "error", "data": json.dumps({"detail": "job not found"})}
            return

        yield {"event": "job.snapshot", "data": json.dumps(_public_view(doc), default=str)}

        if doc["status"] in TERMINAL_STATUSES:
            yield {"event": f"job.{doc['status']}", "data": json.dumps({"status": doc["status"]})}
            return

        while True:
            if await request.is_disconnected():
                break
            message = await pubsub.get_message(
                timeout=KEEPALIVE_TIMEOUT_S, ignore_subscribe_messages=True
            )
            if message is None:
                yield {"comment": "keepalive"}
                continue

            payload = json.loads(message["data"])
            yield {"event": payload["type"], "data": json.dumps(payload["data"], default=str)}
            if payload["type"] in {f"job.{status}" for status in TERMINAL_STATUSES}:
                break


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> EventSourceResponse:
    doc = await jobs_collection().find_one({"id": job_id}, {"id": 1})
    if doc is None:
        raise HTTPException(status_code=404, detail="job not found")
    return EventSourceResponse(_event_stream(job_id, request))
