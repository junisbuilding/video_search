from __future__ import annotations

from unittest.mock import MagicMock

from videosearch.search.models import SearchResponse
from videosearch.search.searcher import Searcher
from videosearch.storage.schemas import (
    SIGLIP_DIM,
    TEXT_EMBED_DIM,
    CaptionEmbeddingRow,
    FrameEmbeddingRow,
)


def _frame_row(video_id: str, frame_idx: int, ts: float) -> FrameEmbeddingRow:
    return FrameEmbeddingRow(
        video_id=video_id,
        frame_idx=frame_idx,
        timestamp_sec=ts,
        embedding=[0.1] * SIGLIP_DIM,
        thumb_path=f"/tmp/{video_id}_{frame_idx}.jpg",
    )


def _caption_row(video_id: str, scene_idx: int) -> CaptionEmbeddingRow:
    return CaptionEmbeddingRow(
        video_id=video_id,
        scene_idx=scene_idx,
        start_sec=0.0,
        end_sec=5.0,
        caption="a scene",
        embedding=[0.1] * TEXT_EMBED_DIM,
    )


def _make_searcher(
    frame_hits: list[FrameEmbeddingRow],
    caption_hits: list[CaptionEmbeddingRow],
    nearest: FrameEmbeddingRow | None = None,
) -> Searcher:
    frames = MagicMock()
    captions = MagicMock()
    image_emb = MagicMock()
    text_emb = MagicMock()

    image_emb.embed_text.return_value = [0.1] * SIGLIP_DIM
    text_emb.embed_text.return_value = [[0.1] * TEXT_EMBED_DIM]
    frames.search.return_value = frame_hits
    captions.search.return_value = caption_hits
    frames.list_for_video.return_value = [nearest] if nearest else []

    return Searcher(frames=frames, captions=captions, image_embedder=image_emb, text_embedder=text_emb)


def test_search_returns_search_response():
    searcher = _make_searcher(
        frame_hits=[_frame_row("v1", 0, 1.0)],
        caption_hits=[],
    )
    result = searcher.search("test query")
    assert isinstance(result, SearchResponse)
    assert result.query == "test query"


def test_search_groups_moments_by_video():
    searcher = _make_searcher(
        frame_hits=[_frame_row("v1", 0, 1.0), _frame_row("v2", 0, 1.0)],
        caption_hits=[],
    )
    result = searcher.search("test")
    assert len(result.results) == 2
    video_ids = {r.video_id for r in result.results}
    assert video_ids == {"v1", "v2"}


def test_search_returns_empty_for_no_hits():
    searcher = _make_searcher(frame_hits=[], caption_hits=[])
    result = searcher.search("nothing")
    assert result.results == ()


def test_caption_hit_calls_find_nearest():
    nearest = _frame_row("v1", 0, 0.5)
    searcher = _make_searcher(
        frame_hits=[],
        caption_hits=[_caption_row("v1", 0)],
        nearest=nearest,
    )
    result = searcher.search("scene query")
    assert len(result.results) == 1
    moment = result.results[0].moments[0]
    assert moment.caption == "a scene"
    assert moment.thumb_path == nearest.thumb_path


def test_search_respects_k_limit():
    searcher = _make_searcher(
        frame_hits=[_frame_row("v1", 0, 1.0), _frame_row("v2", 0, 2.0)],
        caption_hits=[],
    )
    result = searcher.search("query", k=1)
    assert len(result.results) == 1


def test_results_sorted_by_top_score_descending():
    # v1 appears in both frame and caption hits (higher RRF score)
    # v2 appears only in frame hits
    searcher = _make_searcher(
        frame_hits=[_frame_row("v1", 0, 1.0), _frame_row("v2", 0, 1.0)],
        caption_hits=[_caption_row("v1", 0)],
        nearest=_frame_row("v1", 0, 0.5),
    )
    result = searcher.search("query")
    assert result.results[0].video_id == "v1"
    assert result.results[0].top_score > result.results[1].top_score


def test_frame_hit_carries_frame_idx():
    searcher = _make_searcher(
        frame_hits=[_frame_row("v1", 7, 1.0)],
        caption_hits=[],
    )
    result = searcher.search("query")
    assert result.results[0].moments[0].frame_idx == 7


def test_caption_hit_carries_frame_idx_from_nearest():
    nearest = _frame_row("v1", 5, 0.5)
    searcher = _make_searcher(
        frame_hits=[],
        caption_hits=[_caption_row("v1", 0)],
        nearest=nearest,
    )
    result = searcher.search("scene query")
    assert result.results[0].moments[0].frame_idx == 5


def test_caption_hit_with_no_frames_produces_frame_idx_none():
    searcher = _make_searcher(
        frame_hits=[],
        caption_hits=[_caption_row("v1", 0)],
        nearest=None,
    )
    result = searcher.search("scene query")
    assert result.results[0].moments[0].frame_idx is None
