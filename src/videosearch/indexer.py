from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from videosearch.models.protocols import Captioner, ImageEmbedder, TextEmbedder
from videosearch.scanning.frames import (
    FrameSample,
    Scene,
    detect_scenes,
    sample_frames,
)
from videosearch.scanning.hashing import content_hash
from videosearch.scanning.probe import probe
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.schemas import (
    CaptionEmbeddingRow,
    FrameEmbeddingRow,
    VideoRow,
)
from videosearch.storage.videos import VideosRepo


@dataclass(frozen=True)
class IndexResult:
    video_id: str
    hash: str
    status: str
    skipped_reason: str | None = None  # already_indexed | restored_from_missing | path_updated | None


def index_video(
    *,
    path: Path,
    videos: VideosRepo,
    frames: FrameEmbeddingsRepo,
    captions: CaptionEmbeddingsRepo,
    image_embedder: ImageEmbedder,
    text_embedder: TextEmbedder,
    captioner: Captioner,
    work_dir: Path,
    frame_fps: float = 1.0,
    scene_detection: bool = True,
    library_folder_id: str | None = None,
    caption_prompt: str = "Describe what's happening in this scene in one or two sentences.",
) -> IndexResult:
    """Run the full ingestion pipeline for one video file. Synchronous."""
    path = Path(path).resolve()
    h = content_hash(path)

    existing = videos.find_by_hash(h)
    if existing is not None:
        return _resolve_existing(existing, path, videos)

    info = probe(path)
    video_id = str(uuid.uuid4())
    now = time.time()
    row = VideoRow(
        id=video_id,
        path=str(path),
        hash=h,
        duration_sec=info.duration_sec,
        fps=info.fps,
        width=info.width,
        height=info.height,
        mtime=path.stat().st_mtime,
        status="pending",
        last_seen_at=now,
        library_folder_id=library_folder_id,
    )
    videos.insert(row)

    try:
        thumbs_dir = work_dir / video_id / "thumbs"
        samples = list(sample_frames(path, fps=frame_fps, output_dir=thumbs_dir))
        _write_frame_embeddings(frames, video_id, samples, image_embedder)

        if scene_detection:
            scenes = detect_scenes(path, fallback_duration_sec=info.duration_sec)
        else:
            scenes = _fallback_scenes(info.duration_sec)
        _write_caption_embeddings(
            captions, video_id, scenes, samples, captioner, text_embedder, caption_prompt
        )

        videos.update(video_id, status="indexed", indexed_at=time.time(), error=None)
        return IndexResult(video_id=video_id, hash=h, status="indexed")
    except Exception as e:
        videos.update(video_id, status="failed", error=str(e))
        raise


def _resolve_existing(existing: VideoRow, path: Path, videos: VideosRepo) -> IndexResult:
    """Handle hash hits: update path, restore missing, otherwise no-op."""
    updates: dict = {"last_seen_at": time.time()}
    skipped = "already_indexed"
    if str(path) != existing.path:
        updates["path"] = str(path)
        skipped = "path_updated"
    if existing.status == "missing":
        # Restore to indexed if embeddings already exist; otherwise resume on next ingest.
        updates["status"] = "indexed"
        skipped = "restored_from_missing"
    videos.update(existing.id, **updates)
    return IndexResult(
        video_id=existing.id,
        hash=existing.hash,
        status=updates.get("status", existing.status),
        skipped_reason=skipped,
    )


def _fallback_scenes(duration_sec: float, *, window_sec: float = 8.0) -> list[Scene]:
    """Used when scene detection is disabled — fixed-window scene chunks."""
    if duration_sec <= 0:
        return [Scene(scene_idx=0, start_sec=0.0, end_sec=0.0)]
    out: list[Scene] = []
    start = 0.0
    idx = 0
    while start < duration_sec:
        end = min(start + window_sec, duration_sec)
        out.append(Scene(scene_idx=idx, start_sec=start, end_sec=end))
        start = end
        idx += 1
    return out


def _write_frame_embeddings(
    repo: FrameEmbeddingsRepo,
    video_id: str,
    samples: list[FrameSample],
    embedder: ImageEmbedder,
    batch_size: int = 16,
) -> None:
    if not samples:
        return
    for i in range(0, len(samples), batch_size):
        batch = samples[i : i + batch_size]
        vecs = embedder.embed_images([s.path for s in batch])
        rows = [
            FrameEmbeddingRow(
                video_id=video_id,
                frame_idx=s.frame_idx,
                timestamp_sec=s.timestamp_sec,
                embedding=v,
                thumb_path=str(s.path),
            )
            for s, v in zip(batch, vecs, strict=True)
        ]
        repo.insert_many(rows)


def _write_caption_embeddings(
    repo: CaptionEmbeddingsRepo,
    video_id: str,
    scenes: list[Scene],
    samples: list[FrameSample],
    captioner: Captioner,
    text_embedder: TextEmbedder,
    prompt: str,
) -> None:
    if not scenes:
        return
    captions: list[str] = []
    for scene in scenes:
        rep = _representative_frames(scene, samples, max_n=3)
        if not rep:
            captions.append("")
            continue
        captions.append(captioner.caption([s.path for s in rep], prompt=prompt))
    vecs = text_embedder.embed_text(captions)
    rows = [
        CaptionEmbeddingRow(
            video_id=video_id,
            scene_idx=scene.scene_idx,
            start_sec=scene.start_sec,
            end_sec=scene.end_sec,
            caption=cap,
            embedding=vec,
        )
        for scene, cap, vec in zip(scenes, captions, vecs, strict=True)
    ]
    repo.insert_many(rows)


def _representative_frames(
    scene: Scene, samples: list[FrameSample], *, max_n: int
) -> list[FrameSample]:
    in_scene = [s for s in samples if scene.start_sec <= s.timestamp_sec < scene.end_sec]
    if not in_scene:
        # Fall back to the closest single frame to the scene midpoint.
        if not samples:
            return []
        mid = (scene.start_sec + scene.end_sec) / 2
        return [min(samples, key=lambda s: abs(s.timestamp_sec - mid))]
    if len(in_scene) <= max_n:
        return in_scene
    step = len(in_scene) / max_n
    return [in_scene[int(i * step)] for i in range(max_n)]
