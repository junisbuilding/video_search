import time
import uuid
from pathlib import Path

from videosearch.storage.db import Database
from videosearch.storage.schemas import VideoRow
from videosearch.storage.videos import VideosRepo


def _video(**overrides) -> VideoRow:
    now = time.time()
    base = dict(
        id=str(uuid.uuid4()),
        path="/tmp/movie.mp4",
        hash="abc123",
        duration_sec=10.0,
        fps=30.0,
        width=320,
        height=240,
        mtime=now,
        status="pending",
        error=None,
        indexed_at=None,
        library_folder_id=None,
        last_seen_at=now,
    )
    base.update(overrides)
    return VideoRow(**base)


def test_insert_and_find_by_hash(tmp_path: Path):
    repo = VideosRepo(Database(tmp_path))
    v = _video(hash="hashA")
    repo.insert(v)
    found = repo.find_by_hash("hashA")
    assert found is not None
    assert found.id == v.id


def test_find_by_hash_returns_none_when_missing(tmp_path: Path):
    repo = VideosRepo(Database(tmp_path))
    assert repo.find_by_hash("nope") is None


def test_update_status(tmp_path: Path):
    repo = VideosRepo(Database(tmp_path))
    v = _video(hash="h", status="pending")
    repo.insert(v)
    repo.update(v.id, status="indexed", indexed_at=123.0)
    found = repo.find_by_hash("h")
    assert found is not None
    assert found.status == "indexed"
    assert found.indexed_at == 123.0


def test_list_by_status(tmp_path: Path):
    repo = VideosRepo(Database(tmp_path))
    repo.insert(_video(hash="h1", status="indexed"))
    repo.insert(_video(hash="h2", status="indexed"))
    repo.insert(_video(hash="h3", status="failed"))
    indexed = repo.list_by_status("indexed")
    assert len(indexed) == 2
