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
