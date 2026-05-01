from pathlib import Path

from videosearch.indexer import index_video
from videosearch.models.stubs import StubCaptioner, StubImageEmbedder, StubTextEmbedder
from videosearch.search.models import SearchResponse
from videosearch.search.searcher import Searcher
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.db import Database
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.videos import VideosRepo


def test_search_finds_indexed_video(tmp_path: Path, tiny_video: Path):
    db = Database(tmp_path / "data")
    videos = VideosRepo(db)
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)

    image_embedder = StubImageEmbedder()
    text_embedder = StubTextEmbedder()
    captioner = StubCaptioner()

    result = index_video(
        path=tiny_video,
        videos=videos,
        frames=frames,
        captions=captions,
        image_embedder=image_embedder,
        text_embedder=text_embedder,
        captioner=captioner,
        work_dir=tmp_path / "work",
        frame_fps=2.0,
    )
    assert result.status == "indexed"

    searcher = Searcher(
        frames=frames,
        captions=captions,
        image_embedder=image_embedder,
        text_embedder=text_embedder,
    )
    response = searcher.search("a test query")

    assert isinstance(response, SearchResponse)
    assert response.query == "a test query"
    assert len(response.results) == 1
    assert response.results[0].video_id == result.video_id
    assert len(response.results[0].moments) >= 1
    assert response.results[0].top_score > 0.0


def test_search_returns_moments_with_timestamps(tmp_path: Path, tiny_video: Path):
    db = Database(tmp_path / "data")
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)

    index_video(
        path=tiny_video,
        videos=VideosRepo(db),
        frames=frames,
        captions=captions,
        image_embedder=StubImageEmbedder(),
        text_embedder=StubTextEmbedder(),
        captioner=StubCaptioner(),
        work_dir=tmp_path / "work",
        frame_fps=2.0,
    )

    searcher = Searcher(
        frames=frames,
        captions=captions,
        image_embedder=StubImageEmbedder(),
        text_embedder=StubTextEmbedder(),
    )
    response = searcher.search("query")

    assert response.results, "Expected at least one search result after indexing"
    assert response.results[0].moments, "Expected at least one moment in the first result"
    for video_result in response.results:
        for moment in video_result.moments:
            assert moment.timestamp_sec >= 0.0
            assert moment.score > 0.0


def test_search_empty_db_returns_empty(tmp_path: Path):
    db = Database(tmp_path / "data")
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)

    searcher = Searcher(
        frames=frames,
        captions=captions,
        image_embedder=StubImageEmbedder(),
        text_embedder=StubTextEmbedder(),
    )
    response = searcher.search("anything")
    assert response.results == []
