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


def test_list_recent_returns_all_statuses(tmp_path):
    q = JobsQueue(tmp_path / "jobs.db")
    id1 = q.enqueue(kind="index", path="/a.mp4")
    id2 = q.enqueue(kind="index", path="/b.mp4")
    q.claim()
    q.complete(id1)
    jobs = q.list_recent(limit=10)
    by_id = {j.id: j for j in jobs}
    assert id1 in by_id
    assert id2 in by_id
    assert by_id[id1].status == "completed"
    assert by_id[id2].status in ("pending", "in_progress")
    q.close()


def test_enqueue_stores_path_and_folder_id(tmp_path):
    q = JobsQueue(tmp_path / "jobs.db")
    job_id = q.enqueue(kind="index", path="/videos/clip.mp4", library_folder_id="folder-1")
    jobs = q.list_recent(limit=10)
    job = next(j for j in jobs if j.id == job_id)
    assert job.path == "/videos/clip.mp4"
    assert job.library_folder_id == "folder-1"
    q.close()


def test_get_by_id_returns_job(tmp_path):
    q = JobsQueue(tmp_path / "jobs.db")
    job_id = q.enqueue(kind="index", path="/a.mp4")
    job = q.get_by_id(job_id)
    assert job is not None
    assert job.id == job_id
    q.close()


def test_update_video_id_sets_field(tmp_path):
    q = JobsQueue(tmp_path / "jobs.db")
    job_id = q.enqueue(kind="index", path="/a.mp4")
    q.update_video_id(job_id, "video-uuid-1")
    job = q.get_by_id(job_id)
    assert job.video_id == "video-uuid-1"
    q.close()
