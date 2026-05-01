from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from videosearch.api.worker import IndexerWorker
from videosearch.storage.jobs import Job


def _make_job(
    job_id: str = "j1",
    path: str = "/tmp/video.mp4",
    library_folder_id: str | None = None,
) -> Job:
    return Job(
        id=job_id,
        video_id=None,
        path=path,
        library_folder_id=library_folder_id,
        kind="index",
        status="in_progress",
        progress=0.0,
        error=None,
        created_at=time.time(),
        updated_at=time.time(),
    )


def _make_worker(jobs, broadcaster=None) -> IndexerWorker:
    return IndexerWorker(
        jobs=jobs,
        videos=MagicMock(),
        frames=MagicMock(),
        captions=MagicMock(),
        image_embedder=MagicMock(),
        text_embedder=MagicMock(),
        captioner=MagicMock(),
        work_dir=Path("/tmp/work"),
        broadcaster=broadcaster or MagicMock(),
        frame_fps=1.0,
        scene_detection=False,
    )


def test_worker_processes_job_and_broadcasts_completed():
    jobs = MagicMock()
    broadcaster = MagicMock()

    from videosearch.indexer import IndexResult
    with patch("videosearch.api.worker.index_video") as mock_index:
        mock_index.return_value = IndexResult(video_id="v1", hash="abc", status="indexed")
        worker = _make_worker(jobs, broadcaster)
        worker._process(_make_job())

    jobs.complete.assert_called_once_with("j1")
    calls = [c[0][0] for c in broadcaster.broadcast.call_args_list]
    statuses = [c["status"] for c in calls]
    assert "in_progress" in statuses
    assert "completed" in statuses


def test_worker_broadcasts_failed_on_exception():
    jobs = MagicMock()
    broadcaster = MagicMock()

    with patch("videosearch.api.worker.index_video", side_effect=RuntimeError("boom")):
        worker = _make_worker(jobs, broadcaster)
        worker._process(_make_job())

    jobs.fail.assert_called_once()
    calls = [c[0][0] for c in broadcaster.broadcast.call_args_list]
    statuses = [c["status"] for c in calls]
    assert "failed" in statuses


def test_worker_fails_job_when_path_is_none():
    jobs = MagicMock()
    broadcaster = MagicMock()
    job = Job(id="j1", video_id=None, path=None, library_folder_id=None,
              kind="index", status="in_progress", progress=0.0, error=None,
              created_at=time.time(), updated_at=time.time())
    worker = _make_worker(jobs, broadcaster)
    worker._process(job)
    jobs.fail.assert_called_once_with("j1", error="job has no path")


def test_worker_stops_cleanly():
    jobs = MagicMock()
    jobs.claim.return_value = None
    worker = _make_worker(jobs)
    worker.start()
    time.sleep(0.05)
    worker.stop()
    worker.join(timeout=2.0)
    assert not worker.is_alive()
