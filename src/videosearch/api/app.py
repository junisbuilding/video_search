from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from videosearch.api import deps
from videosearch.api.ws import JobBroadcaster, make_ws_router
from videosearch.config import Settings


def create_app(settings: Settings, *, startup: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if startup:
            from videosearch.models.bge import BgeTextEmbedder
            from videosearch.models.llama_cpp_captioner import LlamaCppCaptioner
            from videosearch.models.loader import resolve_gguf
            from videosearch.models.siglip import SiglipEmbedder
            from videosearch.search import Searcher
            from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
            from videosearch.storage.db import Database
            from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
            from videosearch.storage.jobs import JobsQueue
            from videosearch.storage.library_folders import LibraryFoldersRepo
            from videosearch.storage.videos import VideosRepo
            from videosearch.api.worker import IndexerWorker

            if not settings.vlm_model or not settings.vlm_mmproj:
                raise RuntimeError(
                    "VS_VLM_MODEL and VS_VLM_MMPROJ must be set."
                )

            image_embedder = SiglipEmbedder(settings.siglip_model)
            text_embedder = BgeTextEmbedder(settings.text_embedder)
            vlm_path = resolve_gguf(settings.vlm_model, cache_dir=settings.models_dir)
            mmproj_path = resolve_gguf(settings.vlm_mmproj, cache_dir=settings.models_dir)
            captioner = LlamaCppCaptioner(
                str(vlm_path), str(mmproj_path),
                n_gpu_layers=settings.vlm_n_gpu_layers,
            )

            db = Database(settings.data_dir)
            jobs_queue = JobsQueue(settings.data_dir / "jobs.db")
            videos = VideosRepo(db)
            frames = FrameEmbeddingsRepo(db)
            captions = CaptionEmbeddingsRepo(db)
            folders = LibraryFoldersRepo(db)
            searcher = Searcher(
                frames=frames, captions=captions,
                image_embedder=image_embedder, text_embedder=text_embedder,
            )

            loop = asyncio.get_running_loop()
            broadcaster = JobBroadcaster(loop)

            worker = IndexerWorker(
                jobs=jobs_queue, videos=videos, frames=frames, captions=captions,
                image_embedder=image_embedder, text_embedder=text_embedder,
                captioner=captioner, work_dir=settings.data_dir / "work",
                broadcaster=broadcaster, frame_fps=settings.frame_fps,
                scene_detection=settings.scene_detection,
            )
            worker.start()

            app.state.settings = settings
            app.state.searcher = searcher
            app.state.jobs_queue = jobs_queue
            app.state.videos_repo = videos
            app.state.frames_repo = frames
            app.state.captions_repo = captions
            app.state.library_folders_repo = folders
            app.state.broadcaster = broadcaster
            app.state.worker = worker

            yield

            worker.stop()
            worker.join(timeout=10)
            jobs_queue.close()
        else:
            yield

    app = FastAPI(lifespan=lifespan, title="Video Search API")

    from videosearch.api.routers import (
        fs, health, ingest, jobs, library, search,
        settings as settings_router, videos,
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(library.router, prefix="/api")
    app.include_router(ingest.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(videos.router, prefix="/api")
    app.include_router(fs.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(make_ws_router(deps.get_broadcaster, deps.get_jobs_queue))

    return app
