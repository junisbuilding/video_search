from __future__ import annotations

import torch
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from videosearch.api.deps import get_videos_repo
from videosearch.storage.videos import VideosRepo

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    db: bool
    models_loaded: bool
    gpu_backend: str
    indexed_count: int


@router.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    videos: VideosRepo = Depends(get_videos_repo),
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
    return HealthResponse(
        status=status,
        db=db_ok,
        models_loaded=models_loaded,
        gpu_backend=gpu_backend,
        indexed_count=indexed_count,
    )
