from __future__ import annotations

from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from videosearch.api import deps
from videosearch.api.app import create_app
from videosearch.config import Settings
from videosearch.models.stubs import StubCaptioner, StubImageEmbedder, StubTextEmbedder
from videosearch.search import Searcher
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.db import Database
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.jobs import JobsQueue
from videosearch.storage.library_folders import LibraryFoldersRepo
from videosearch.storage.videos import VideosRepo


class IntegrationFixture(NamedTuple):
    client: TestClient
    jobs_queue: JobsQueue
    videos: VideosRepo
    frames: FrameEmbeddingsRepo
    captions: CaptionEmbeddingsRepo
    image_embedder: StubImageEmbedder
    text_embedder: StubTextEmbedder
    captioner: StubCaptioner
    settings: Settings
    tiny_video: Path


@pytest.fixture
def integration_client(tmp_path, tiny_video):
    """Full app with real DB + stub models, no lifespan (worker started manually)."""
    settings = Settings(
        data_dir=tmp_path / "data",
        models_dir=tmp_path / "models",
    )
    db = Database(settings.data_dir)
    jobs_queue = JobsQueue(settings.data_dir / "jobs.db")
    videos = VideosRepo(db)
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)
    folders = LibraryFoldersRepo(db)
    image_embedder = StubImageEmbedder()
    text_embedder = StubTextEmbedder()
    captioner = StubCaptioner()
    searcher = Searcher(
        frames=frames, captions=captions,
        image_embedder=image_embedder, text_embedder=text_embedder,
    )

    app = create_app(settings, startup=False)
    app.state.settings = settings
    app.state.searcher = searcher
    app.state.jobs_queue = jobs_queue
    app.state.videos_repo = videos
    app.state.frames_repo = frames
    app.state.captions_repo = captions
    app.state.library_folders_repo = folders
    app.state.broadcaster = MagicMock()
    app.state.worker = MagicMock()
    from videosearch.scanning.watcher import LibraryWatcher
    watcher = LibraryWatcher(jobs_queue, videos)
    watcher.start()
    app.state.library_watcher = watcher
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        yield IntegrationFixture(
            client=client,
            jobs_queue=jobs_queue,
            videos=videos,
            frames=frames,
            captions=captions,
            image_embedder=image_embedder,
            text_embedder=text_embedder,
            captioner=captioner,
            settings=settings,
            tiny_video=tiny_video,
        )
    watcher.stop()


def test_integration_ingest_then_search(integration_client):
    from videosearch.indexer import index_video

    fx = integration_client
    result = index_video(
        path=fx.tiny_video,
        videos=fx.videos,
        frames=fx.frames,
        captions=fx.captions,
        image_embedder=fx.image_embedder,
        text_embedder=fx.text_embedder,
        captioner=fx.captioner,
        work_dir=fx.settings.data_dir / "work",
        frame_fps=2.0,
    )
    assert result.status == "indexed"

    r = fx.client.post("/api/search", json={"query": "test query"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) >= 1
    assert data["results"][0]["video_id"] == result.video_id


def test_integration_health_endpoint(integration_client):
    r = integration_client.client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["db"] is True


def test_integration_ingest_endpoint_enqueues_job(integration_client, tmp_path):
    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"x" * 200_000)

    r = integration_client.client.post("/api/ingest", json={"path": str(video_file)})
    assert r.status_code == 200
    job_ids = r.json()["enqueued"]
    assert len(job_ids) == 1

    job = integration_client.jobs_queue.get_by_id(job_ids[0])
    assert job is not None
    assert job.path == str(video_file)


def test_integration_jobs_list_after_ingest(integration_client, tmp_path):
    video_file = tmp_path / "sample2.mp4"
    video_file.write_bytes(b"x" * 200_000)
    integration_client.client.post("/api/ingest", json={"path": str(video_file)})

    r = integration_client.client.get("/api/jobs")
    assert r.status_code == 200
    jobs = r.json()["jobs"]
    assert len(jobs) >= 1
    assert any(j["path"] == str(video_file) for j in jobs)
