from __future__ import annotations

from fastapi import HTTPException
from starlette.requests import HTTPConnection

from videosearch.api.worker import IndexerWorker
from videosearch.api.ws import JobBroadcaster
from videosearch.config import Settings
from videosearch.models.downloader import ModelDownloader
from videosearch.scanning.watcher import LibraryWatcher
from videosearch.search import Searcher
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.jobs import JobsQueue
from videosearch.storage.library_folders import LibraryFoldersRepo
from videosearch.storage.videos import VideosRepo


def get_settings(conn: HTTPConnection) -> Settings:
    return conn.app.state.settings


def get_searcher(conn: HTTPConnection) -> Searcher:
    if not hasattr(conn.app.state, "searcher"):
        raise HTTPException(
            status_code=503,
            detail="Models not loaded. Set vlm_model and vlm_mmproj in Settings and restart.",
        )
    return conn.app.state.searcher


def get_jobs_queue(conn: HTTPConnection) -> JobsQueue:
    return conn.app.state.jobs_queue


def get_videos_repo(conn: HTTPConnection) -> VideosRepo:
    return conn.app.state.videos_repo


def get_frames_repo(conn: HTTPConnection) -> FrameEmbeddingsRepo:
    return conn.app.state.frames_repo


def get_captions_repo(conn: HTTPConnection) -> CaptionEmbeddingsRepo:
    return conn.app.state.captions_repo


def get_library_folders_repo(conn: HTTPConnection) -> LibraryFoldersRepo:
    return conn.app.state.library_folders_repo


def get_broadcaster(conn: HTTPConnection) -> JobBroadcaster:
    return conn.app.state.broadcaster


def get_worker(conn: HTTPConnection) -> IndexerWorker:
    return conn.app.state.worker


def get_downloader(conn: HTTPConnection) -> ModelDownloader:
    return conn.app.state.downloader


def get_library_watcher(conn: HTTPConnection) -> LibraryWatcher:
    return conn.app.state.library_watcher
