from __future__ import annotations

import mimetypes
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import FileResponse

from videosearch.api.deps import get_frames_repo, get_videos_repo
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.videos import VideosRepo

router = APIRouter()


@router.get("/videos/{video_id}/stream")
async def stream_video(
    video_id: str,
    videos: VideosRepo = Depends(get_videos_repo),
) -> FileResponse:
    video = videos.find_by_id(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    if video.status == "missing":
        raise HTTPException(status_code=410, detail="video file is missing")
    path = Path(video.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="video file not found on disk")
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=media_type or "application/octet-stream")


@router.get("/videos/{video_id}/thumbs/{frame_idx}")
async def get_thumbnail(
    video_id: str,
    frame_idx: int,
    frames: FrameEmbeddingsRepo = Depends(get_frames_repo),
) -> FileResponse:
    row = frames.find_frame(video_id, frame_idx)
    if row is None:
        raise HTTPException(status_code=404, detail="thumbnail not found")
    path = Path(row.thumb_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="thumbnail file not found on disk")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/videos/{video_id}/reveal")
async def reveal_video(
    video_id: str,
    videos: VideosRepo = Depends(get_videos_repo),
) -> dict:
    video = videos.find_by_id(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    path = Path(video.path)
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise HTTPException(status_code=501, detail="no display available")
        subprocess.Popen(["xdg-open", str(path.parent)])
    return {"ok": True}
