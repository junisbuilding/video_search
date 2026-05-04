from __future__ import annotations

import torch
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from videosearch.api.deps import get_library_watcher, get_videos_repo
from videosearch.scanning.watcher import LibraryWatcher
from videosearch.storage.videos import VideosRepo

router = APIRouter()


class WatcherStatus(BaseModel):
    folder_id: str
    path: str
    active: bool
    error: str | None


class HealthResponse(BaseModel):
    status: str
    db: bool
    models_loaded: bool
    gpu_backend: str
    indexed_count: int
    watchers: list[WatcherStatus]


@router.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    videos: VideosRepo = Depends(get_videos_repo),
    watcher: LibraryWatcher = Depends(get_library_watcher),
) -> HealthResponse:
    db_ok = True
    indexed_count = 0
    try:
        rows = videos.list_by_status("indexed")
        indexed_count = len(rows)
    except Exception:
        db_ok = False

    models_loaded = hasattr(request.app.state, "searcher")

    if torch.backends.mps.is_available():
        gpu_backend = "mps"
    elif torch.cuda.is_available():
        gpu_backend = "cuda"
    else:
        gpu_backend = "cpu"

    status = "ok" if (db_ok and models_loaded) else "degraded"
    watcher_statuses = [
        WatcherStatus(folder_id=s.folder_id, path=s.path, active=s.active, error=s.error)
        for s in watcher.status()
    ]
    return HealthResponse(
        status=status,
        db=db_ok,
        models_loaded=models_loaded,
        gpu_backend=gpu_backend,
        indexed_count=indexed_count,
        watchers=watcher_statuses,
    )
