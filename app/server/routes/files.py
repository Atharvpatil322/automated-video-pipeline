"""Serve files out of a job's run directory. Strict path-traversal
protection (app/server/security.safe_join raises on any escape attempt),
and Range support (so a browser <video> element can seek final.mp4) comes
from Starlette's own FileResponse, which honors a Range request header
and returns 206 Partial Content automatically.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.server.auth import require_api_token
from app.server.db import jobs_collection
from app.server.security import PathTraversalError, safe_join

router = APIRouter(prefix="/api/v1", tags=["files"], dependencies=[Depends(require_api_token)])


@router.get("/jobs/{job_id}/files/{file_path:path}")
async def get_job_file(job_id: str, file_path: str) -> FileResponse:
    doc = await jobs_collection().find_one({"id": job_id}, {"run_dir": 1})
    if doc is None or not doc.get("run_dir"):
        raise HTTPException(status_code=404, detail="job or run directory not found")

    run_dir = Path(doc["run_dir"])
    try:
        resolved = safe_join(run_dir, file_path)
    except PathTraversalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="file not found")

    return FileResponse(resolved)
