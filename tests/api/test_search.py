from __future__ import annotations

import time

from videosearch.search.models import Moment, SearchResponse, VideoResult
from videosearch.storage.schemas import VideoRow


def _video_row(id_: str = "v1", status: str = "indexed") -> VideoRow:
    return VideoRow(
        id=id_, path=f"/videos/{id_}.mp4", hash=id_,
        duration_sec=60.0, fps=30.0, width=1920, height=1080,
        mtime=time.time(), status=status, last_seen_at=time.time(),
    )


def _search_response(video_id: str = "v1", frame_idx: int = 3) -> SearchResponse:
    return SearchResponse(
        query="test query",
        results=(
            VideoResult(
                video_id=video_id,
                top_score=0.9,
                moments=(
                    Moment(
                        timestamp_sec=1.0, score=0.9,
                        thumb_path="/tmp/thumb.jpg",
                        frame_idx=frame_idx,
                    ),
                ),
            ),
        ),
    )


def test_search_returns_200_with_results(client, mock_searcher, mock_videos):
    mock_searcher.search.return_value = _search_response()
    mock_videos.find_by_id.return_value = _video_row()

    r = client.post("/api/search", json={"query": "test query"})

    assert r.status_code == 200
    data = r.json()
    assert data["query"] == "test query"
    assert len(data["results"]) == 1
    assert data["results"][0]["video_id"] == "v1"
    assert data["results"][0]["path"] == "/videos/v1.mp4"


def test_search_constructs_thumb_url_from_frame_idx(client, mock_searcher, mock_videos):
    mock_searcher.search.return_value = _search_response(frame_idx=7)
    mock_videos.find_by_id.return_value = _video_row()

    r = client.post("/api/search", json={"query": "test"})

    moment = r.json()["results"][0]["moments"][0]
    assert moment["thumb_url"] == "/api/videos/v1/thumbs/7"


def test_search_filters_missing_videos_by_default(client, mock_searcher, mock_videos):
    mock_searcher.search.return_value = _search_response()
    mock_videos.find_by_id.return_value = _video_row(status="missing")

    r = client.post("/api/search", json={"query": "test"})

    assert r.json()["results"] == []


def test_search_includes_missing_when_requested(client, mock_searcher, mock_videos):
    mock_searcher.search.return_value = _search_response()
    mock_videos.find_by_id.return_value = _video_row(status="missing")

    r = client.post("/api/search", json={"query": "test", "include_missing": True})

    assert len(r.json()["results"]) == 1


def test_search_passes_k_to_searcher(client, mock_searcher, mock_videos):
    mock_searcher.search.return_value = SearchResponse(query="test", results=())

    client.post("/api/search", json={"query": "test", "k": 5})

    mock_searcher.search.assert_called_once_with("test", k=5)
