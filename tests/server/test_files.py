from pathlib import Path

import pytest

from app.schema.job import JobDocument, JobOptions
from app.server.config import set_settings
from app.server.db import jobs_collection
from app.server.security import PathTraversalError, safe_join


async def _insert_job_with_run_dir(job_id: str, run_dir: Path) -> None:
    doc = JobDocument(
        id=job_id, status="completed", options=JobOptions(topic="t"), run_dir=str(run_dir)
    )
    await jobs_collection().insert_one(doc.model_dump(mode="json"))


def test_safe_join_rejects_parent_traversal(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, "../../etc/passwd")


def test_safe_join_rejects_absolute_path_escape(tmp_path, tmp_path_factory):
    other = tmp_path_factory.mktemp("elsewhere")
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, str(other / "secret.txt"))


def test_safe_join_allows_a_normal_relative_path(tmp_path):
    (tmp_path / "final.mp4").write_bytes(b"video")
    resolved = safe_join(tmp_path, "final.mp4")
    assert resolved == (tmp_path / "final.mp4").resolve()


async def test_files_route_blocks_path_traversal(client, fake_db, tmp_path):
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    (run_dir / "final.mp4").write_bytes(b"video-bytes")
    await _insert_job_with_run_dir("job-files-1", run_dir)

    response = await client.get("/api/v1/jobs/job-files-1/files/../../../etc/passwd")
    assert response.status_code in (400, 404)


async def test_files_route_404_for_missing_file(client, tmp_path):
    run_dir = tmp_path / "run2"
    run_dir.mkdir()
    await _insert_job_with_run_dir("job-files-2", run_dir)

    response = await client.get("/api/v1/jobs/job-files-2/files/does-not-exist.mp4")
    assert response.status_code == 404


async def test_files_route_404_for_unknown_job(client):
    response = await client.get("/api/v1/jobs/no-such-job/files/final.mp4")
    assert response.status_code == 404


async def test_files_route_serves_full_file(client, tmp_path):
    run_dir = tmp_path / "run3"
    run_dir.mkdir()
    content = b"0123456789" * 100
    (run_dir / "final.mp4").write_bytes(content)
    await _insert_job_with_run_dir("job-files-3", run_dir)

    response = await client.get("/api/v1/jobs/job-files-3/files/final.mp4")
    assert response.status_code == 200
    assert response.content == content


async def test_files_route_supports_range_requests(client, tmp_path):
    run_dir = tmp_path / "run4"
    run_dir.mkdir()
    content = bytes(range(256)) * 10  # 2560 bytes
    (run_dir / "final.mp4").write_bytes(content)
    await _insert_job_with_run_dir("job-files-4", run_dir)

    response = await client.get(
        "/api/v1/jobs/job-files-4/files/final.mp4", headers={"Range": "bytes=10-19"}
    )
    assert response.status_code == 206
    assert response.content == content[10:20]
    assert response.headers["content-range"] == f"bytes 10-19/{len(content)}"

    # curl -r 10-19 equivalent: `curl -H "Range: bytes=10-19" .../files/final.mp4`


async def test_files_route_accepts_token_query_param_when_api_token_set(
    client, server_settings, tmp_path
):
    """<video>/<img> tags can't send an Authorization header, so the files
    route (only) also accepts the token as ?token=... - every other route
    stays header-only (see test_jobs_api.py / test_events.py).
    """
    server_settings.api_token = "secret-token"
    set_settings(server_settings)
    run_dir = tmp_path / "run5"
    run_dir.mkdir()
    (run_dir / "final.mp4").write_bytes(b"video-bytes")
    await _insert_job_with_run_dir("job-files-5", run_dir)

    no_auth = await client.get("/api/v1/jobs/job-files-5/files/final.mp4")
    assert no_auth.status_code == 401

    wrong_token = await client.get(
        "/api/v1/jobs/job-files-5/files/final.mp4", params={"token": "wrong"}
    )
    assert wrong_token.status_code == 401

    with_query_token = await client.get(
        "/api/v1/jobs/job-files-5/files/final.mp4", params={"token": "secret-token"}
    )
    assert with_query_token.status_code == 200

    with_header = await client.get(
        "/api/v1/jobs/job-files-5/files/final.mp4",
        headers={"Authorization": "Bearer secret-token"},
    )
    assert with_header.status_code == 200
