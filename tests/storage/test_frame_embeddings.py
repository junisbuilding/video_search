from pathlib import Path

from videosearch.storage.db import Database
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.schemas import SIGLIP_DIM, FrameEmbeddingRow


def _frame(video_id: str, idx: int) -> FrameEmbeddingRow:
    return FrameEmbeddingRow(
        video_id=video_id,
        frame_idx=idx,
        timestamp_sec=float(idx),
        embedding=[0.1] * SIGLIP_DIM,
        thumb_path=f"/tmp/{idx}.jpg",
    )


def test_bulk_insert_and_list(tmp_path: Path):
    repo = FrameEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_frame("v1", i) for i in range(3)])
    rows = repo.list_for_video("v1")
    assert len(rows) == 3
    assert sorted(r.frame_idx for r in rows) == [0, 1, 2]


def test_list_for_other_video_empty(tmp_path: Path):
    repo = FrameEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_frame("v1", 0)])
    assert repo.list_for_video("v2") == []


def test_search_returns_limited_rows(tmp_path: Path):
    repo = FrameEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_frame("v1", i) for i in range(5)])
    query = [0.1] * SIGLIP_DIM
    results = repo.search(query, limit=3)
    assert len(results) == 3
    assert all(isinstance(r, FrameEmbeddingRow) for r in results)


def test_find_nearest_returns_closest_by_timestamp(tmp_path: Path):
    repo = FrameEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_frame("v1", i) for i in range(5)])  # timestamps 0.0 .. 4.0
    result = repo.find_nearest("v1", 2.1)
    assert result is not None
    assert result.timestamp_sec == 2.0  # frame_idx=2


def test_find_nearest_returns_none_for_missing_video(tmp_path: Path):
    repo = FrameEmbeddingsRepo(Database(tmp_path))
    assert repo.find_nearest("nonexistent", 0.0) is None


def test_find_frame_returns_correct_row(tmp_path):
    db = Database(tmp_path / "data")
    repo = FrameEmbeddingsRepo(db)
    rows = [
        FrameEmbeddingRow(video_id="v1", frame_idx=1, timestamp_sec=0.0,
                          embedding=[0.1]*SIGLIP_DIM, thumb_path="/t/1.jpg"),
        FrameEmbeddingRow(video_id="v1", frame_idx=2, timestamp_sec=1.0,
                          embedding=[0.1]*SIGLIP_DIM, thumb_path="/t/2.jpg"),
    ]
    repo.insert_many(rows)
    result = repo.find_frame("v1", 2)
    assert result is not None
    assert result.frame_idx == 2
    assert result.thumb_path == "/t/2.jpg"


def test_find_frame_returns_none_when_missing(tmp_path):
    db = Database(tmp_path / "data")
    repo = FrameEmbeddingsRepo(db)
    assert repo.find_frame("v1", 99) is None
