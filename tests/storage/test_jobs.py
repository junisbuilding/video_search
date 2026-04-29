from pathlib import Path

from videosearch.storage.jobs import Job, JobsQueue


def test_enqueue_and_claim_returns_pending(tmp_path: Path):
    q = JobsQueue(tmp_path / "jobs.db")
    q.enqueue(video_id="v1", kind="ingest")
    job = q.claim()
    assert isinstance(job, Job)
    assert job.video_id == "v1"
    assert job.status == "in_progress"


def test_claim_returns_none_when_empty(tmp_path: Path):
    q = JobsQueue(tmp_path / "jobs.db")
    assert q.claim() is None


def test_complete_marks_done(tmp_path: Path):
    q = JobsQueue(tmp_path / "jobs.db")
    q.enqueue(video_id="v1", kind="ingest")
    job = q.claim()
    assert job is not None
    q.complete(job.id)
    # No more pending work
    assert q.claim() is None


def test_fail_records_error(tmp_path: Path):
    q = JobsQueue(tmp_path / "jobs.db")
    q.enqueue(video_id="v1", kind="ingest")
    job = q.claim()
    assert job is not None
    q.fail(job.id, error="boom")
    failed = q.list_by_status("failed")
    assert len(failed) == 1
    assert failed[0].error == "boom"


def test_jobs_persist_across_instances(tmp_path: Path):
    db = tmp_path / "jobs.db"
    JobsQueue(db).enqueue(video_id="v1", kind="ingest")
    job = JobsQueue(db).claim()
    assert job is not None
    assert job.video_id == "v1"
