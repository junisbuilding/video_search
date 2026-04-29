from pathlib import Path

import numpy as np

from videosearch.indexer import index_video
from videosearch.models.stubs import StubCaptioner, StubImageEmbedder, StubTextEmbedder
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.db import Database
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.schemas import SIGLIP_DIM, TEXT_EMBED_DIM
from videosearch.storage.videos import VideosRepo


def test_full_pipeline_produces_expected_data(tmp_path: Path, tiny_video: Path):
    db = Database(tmp_path / "data")
    videos = VideosRepo(db)
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)

    result = index_video(
        path=tiny_video,
        videos=videos,
        frames=frames,
        captions=captions,
        image_embedder=StubImageEmbedder(),
        text_embedder=StubTextEmbedder(),
        captioner=StubCaptioner(),
        work_dir=tmp_path / "work",
        frame_fps=2.0,
    )

    assert result.status == "indexed"
    assert result.skipped_reason is None

    video = videos.find_by_hash(result.hash)
    assert video is not None
    assert video.path == str(tiny_video.resolve())
    assert video.duration_sec > 0
    assert video.width == 320
    assert video.height == 240

    frame_rows = frames.list_for_video(video.id)
    assert len(frame_rows) >= 2
    for r in frame_rows:
        assert len(r.embedding) == SIGLIP_DIM
        assert Path(r.thumb_path).exists()

    caption_rows = captions.list_for_video(video.id)
    assert len(caption_rows) >= 1
    for r in caption_rows:
        assert len(r.embedding) == TEXT_EMBED_DIM
        assert r.modality == "visual_caption"
        assert r.caption  # non-empty string


def test_embeddings_are_unit_finite(tmp_path: Path, tiny_video: Path):
    """Sanity: all stub embeddings should be finite floats in [-1, 1]."""
    db = Database(tmp_path / "data")
    videos = VideosRepo(db)
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)

    result = index_video(
        path=tiny_video,
        videos=videos,
        frames=frames,
        captions=captions,
        image_embedder=StubImageEmbedder(),
        text_embedder=StubTextEmbedder(),
        captioner=StubCaptioner(),
        work_dir=tmp_path / "work",
        frame_fps=2.0,
    )

    for r in frames.list_for_video(result.video_id):
        arr = np.asarray(r.embedding)
        assert np.all(np.isfinite(arr))
        assert np.all(np.abs(arr) <= 1.0)
    for r in captions.list_for_video(result.video_id):
        arr = np.asarray(r.embedding)
        assert np.all(np.isfinite(arr))
        assert np.all(np.abs(arr) <= 1.0)
