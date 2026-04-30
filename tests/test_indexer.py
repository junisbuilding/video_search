from pathlib import Path

from videosearch.indexer import IndexResult, index_video
from videosearch.models.stubs import StubCaptioner, StubImageEmbedder, StubTextEmbedder
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.db import Database
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.videos import VideosRepo


def _services(tmp_path: Path):
    db = Database(tmp_path / "data")
    return {
        "db": db,
        "videos": VideosRepo(db),
        "frames": FrameEmbeddingsRepo(db),
        "captions": CaptionEmbeddingsRepo(db),
        "image_embedder": StubImageEmbedder(),
        "text_embedder": StubTextEmbedder(),
        "captioner": StubCaptioner(),
    }


def test_index_creates_video_row_and_embeddings(tmp_path: Path, tiny_video: Path):
    s = _services(tmp_path)
    work_dir = tmp_path / "work"

    result = index_video(
        path=tiny_video,
        videos=s["videos"],
        frames=s["frames"],
        captions=s["captions"],
        image_embedder=s["image_embedder"],
        text_embedder=s["text_embedder"],
        captioner=s["captioner"],
        work_dir=work_dir,
        frame_fps=2.0,
    )
    assert isinstance(result, IndexResult)
    assert result.status == "indexed"

    v = s["videos"].find_by_hash(result.hash)
    assert v is not None
    assert v.status == "indexed"
    assert v.indexed_at is not None

    frame_rows = s["frames"].list_for_video(v.id)
    caption_rows = s["captions"].list_for_video(v.id)
    assert len(frame_rows) >= 1
    assert len(caption_rows) >= 1


def test_index_is_idempotent(tmp_path: Path, tiny_video: Path):
    s = _services(tmp_path)
    work_dir = tmp_path / "work"
    kwargs = dict(
        path=tiny_video,
        videos=s["videos"],
        frames=s["frames"],
        captions=s["captions"],
        image_embedder=s["image_embedder"],
        text_embedder=s["text_embedder"],
        captioner=s["captioner"],
        work_dir=work_dir,
        frame_fps=2.0,
    )
    r1 = index_video(**kwargs)
    r2 = index_video(**kwargs)
    assert r1.video_id == r2.video_id
    assert r2.skipped_reason == "already_indexed"
    # No duplicate frame rows
    assert len(s["frames"].list_for_video(r1.video_id)) == \
           len(s["frames"].list_for_video(r2.video_id))


def test_index_path_updated(tmp_path: Path, tiny_video: Path):
    s = _services(tmp_path)
    work_dir = tmp_path / "work"
    kwargs = dict(
        path=tiny_video,
        videos=s["videos"],
        frames=s["frames"],
        captions=s["captions"],
        image_embedder=s["image_embedder"],
        text_embedder=s["text_embedder"],
        captioner=s["captioner"],
        work_dir=work_dir,
        frame_fps=2.0,
    )
    r = index_video(**kwargs)
    # Simulate path drift (file was moved since last index)
    s["videos"].update(r.video_id, path="/old/path/video.mp4")

    r2 = index_video(**kwargs)
    assert r2.skipped_reason == "path_updated"
    assert r2.video_id == r.video_id
    v = s["videos"].find_by_id(r.video_id)
    assert v is not None
    assert v.path == str(tiny_video.resolve())


def test_index_restores_missing_to_indexed(tmp_path: Path, tiny_video: Path):
    s = _services(tmp_path)
    work_dir = tmp_path / "work"
    kwargs = dict(
        path=tiny_video,
        videos=s["videos"],
        frames=s["frames"],
        captions=s["captions"],
        image_embedder=s["image_embedder"],
        text_embedder=s["text_embedder"],
        captioner=s["captioner"],
        work_dir=work_dir,
        frame_fps=2.0,
    )
    r = index_video(**kwargs)
    s["videos"].update(r.video_id, status="missing")

    # Re-encounter the same file
    r2 = index_video(**kwargs)
    v = s["videos"].find_by_hash(r.hash)
    assert v is not None
    assert v.status == "indexed"
    assert r2.skipped_reason == "restored_from_missing"


def test_index_resumes_from_failed(tmp_path: Path, tiny_video: Path):
    s = _services(tmp_path)
    work_dir = tmp_path / "work"
    kwargs = dict(
        path=tiny_video,
        videos=s["videos"],
        frames=s["frames"],
        captions=s["captions"],
        image_embedder=s["image_embedder"],
        text_embedder=s["text_embedder"],
        captioner=s["captioner"],
        work_dir=work_dir,
        frame_fps=2.0,
    )
    r = index_video(**kwargs)
    # Force into failed state with a recorded error
    s["videos"].update(r.video_id, status="failed", error="simulated failure")

    r2 = index_video(**kwargs)
    assert r2.skipped_reason == "resumed"
    assert r2.status == "indexed"
    assert r2.video_id == r.video_id
    v = s["videos"].find_by_id(r.video_id)
    assert v is not None
    assert v.status == "indexed"
    assert v.error is None  # error column cleared on successful resume
