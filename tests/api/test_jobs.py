from __future__ import annotations

import time
from videosearch.storage.jobs import Job


def _job(id_: str = "j1", status: str = "completed") -> Job:
    return Job(
        id=id_, video_id="v1", path="/a.mp4", library_folder_id=None,
        kind="index", status=status, progress=1.0, error=None,
        created_at=time.time(), updated_at=time.time(),
    )


def test_list_jobs_returns_recent(client, mock_jobs):
    mock_jobs.list_recent.return_value = [_job("j1"), _job("j2")]
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert len(r.json()["jobs"]) == 2
    mock_jobs.list_recent.assert_called_once_with(200)


def test_retry_job_returns_409_if_not_failed(client, mock_jobs):
    mock_jobs.get_by_id.return_value = _job("j1", status="completed")
    r = client.post("/api/jobs/j1/retry")
    assert r.status_code == 409


def test_retry_job_enqueues_new_job(client, mock_jobs):
    mock_jobs.get_by_id.return_value = _job("j1", status="failed")
    mock_jobs.enqueue.return_value = "j2"
    r = client.post("/api/jobs/j1/retry")
    assert r.status_code == 200
    assert r.json()["job_id"] == "j2"
    mock_jobs.enqueue.assert_called_once()


def test_retry_job_returns_404_for_unknown_id(client, mock_jobs):
    mock_jobs.get_by_id.return_value = None
    r = client.post("/api/jobs/unknown/retry")
    assert r.status_code == 404
