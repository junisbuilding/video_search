from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from videosearch.indexer import index_video
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.jobs import Job, JobsQueue
from videosearch.storage.videos import VideosRepo

if TYPE_CHECKING:
    from videosearch.api.ws import JobBroadcaster


class IndexerWorker(threading.Thread):
    def __init__(
        self,
        *,
        jobs: JobsQueue,
        videos: VideosRepo,
        frames: FrameEmbeddingsRepo,
        captions: CaptionEmbeddingsRepo,
        image_embedder,
        text_embedder,
        captioner,
        work_dir: Path,
        broadcaster: "JobBroadcaster",
        frame_fps: float = 1.0,
        scene_detection: bool = True,
    ) -> None:
        super().__init__(daemon=True, name="indexer-worker")
        self._jobs = jobs
        self._videos = videos
        self._frames = frames
        self._captions = captions
        self._image_embedder = image_embedder
        self._text_embedder = text_embedder
        self._captioner = captioner
        self._work_dir = work_dir
        self._broadcaster = broadcaster
        self._frame_fps = frame_fps
        self._scene_detection = scene_detection
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            job = self._jobs.claim()
            if job is None:
                self._stop_event.wait(timeout=1.0)
                continue
            self._process(job)

    def stop(self) -> None:
        self._stop_event.set()

    def _process(self, job: Job) -> None:
        if not job.path:
            self._jobs.fail(job.id, error="job has no path")
            self._broadcaster.broadcast({
                "job_id": job.id, "video_id": job.video_id,
                "path": job.path,
                "kind": job.kind, "status": "failed",
                "progress": 0.0, "error": "job has no path",
                "created_at": job.created_at, "updated_at": job.updated_at,
            })
            return

        self._broadcaster.broadcast({
            "job_id": job.id, "video_id": job.video_id,
            "path": job.path,
            "kind": job.kind, "status": "in_progress",
            "progress": 0.0, "error": None,
            "created_at": job.created_at, "updated_at": job.updated_at,
        })
        try:
            result = index_video(
                path=Path(job.path),
                videos=self._videos,
                frames=self._frames,
                captions=self._captions,
                image_embedder=self._image_embedder,
                text_embedder=self._text_embedder,
                captioner=self._captioner,
                work_dir=self._work_dir,
                frame_fps=self._frame_fps,
                scene_detection=self._scene_detection,
                library_folder_id=job.library_folder_id,
            )
            self._jobs.update_video_id(job.id, result.video_id)
            self._jobs.complete(job.id)
            self._broadcaster.broadcast({
                "job_id": job.id, "video_id": result.video_id,
                "path": job.path,
                "kind": job.kind, "status": "completed",
                "progress": 1.0, "error": None,
                "created_at": job.created_at, "updated_at": job.updated_at,
            })
        except Exception as e:
            self._jobs.fail(job.id, error=str(e))
            self._broadcaster.broadcast({
                "job_id": job.id, "video_id": job.video_id,
                "path": job.path,
                "kind": job.kind, "status": "failed",
                "progress": 0.0, "error": str(e),
                "created_at": job.created_at, "updated_at": job.updated_at,
            })
