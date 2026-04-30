from pathlib import Path

from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.db import Database
from videosearch.storage.schemas import TEXT_EMBED_DIM, CaptionEmbeddingRow


def _caption(video_id: str, idx: int) -> CaptionEmbeddingRow:
    return CaptionEmbeddingRow(
        video_id=video_id,
        scene_idx=idx,
        start_sec=float(idx),
        end_sec=float(idx) + 1.0,
        caption=f"scene {idx}",
        embedding=[0.2] * TEXT_EMBED_DIM,
    )


def test_bulk_insert_and_list(tmp_path: Path):
    repo = CaptionEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_caption("v1", i) for i in range(2)])
    rows = repo.list_for_video("v1")
    assert len(rows) == 2
    assert sorted(r.scene_idx for r in rows) == [0, 1]


def test_search_returns_limited_rows(tmp_path: Path):
    repo = CaptionEmbeddingsRepo(Database(tmp_path))
    repo.insert_many([_caption("v1", i) for i in range(5)])
    query = [0.2] * TEXT_EMBED_DIM
    results = repo.search(query, limit=3)
    assert len(results) == 3
    assert all(isinstance(r, CaptionEmbeddingRow) for r in results)
