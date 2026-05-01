from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from videosearch.api.deps import get_searcher, get_videos_repo
from videosearch.search import Searcher
from videosearch.storage.videos import VideosRepo

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    k: int = 10
    include_missing: bool = False


class MomentResponse(BaseModel):
    timestamp_sec: float
    score: float
    thumb_url: str | None
    caption: str | None
    source: str  # "frame" | "caption"


class VideoResultResponse(BaseModel):
    video_id: str
    path: str
    duration_sec: float
    top_score: float
    moments: list[MomentResponse]


class SearchApiResponse(BaseModel):
    query: str
    results: list[VideoResultResponse]


@router.post("/search", response_model=SearchApiResponse)
async def search(
    body: SearchRequest,
    searcher: Searcher = Depends(get_searcher),
    videos: VideosRepo = Depends(get_videos_repo),
) -> SearchApiResponse:
    response = searcher.search(body.query, k=body.k)

    results: list[VideoResultResponse] = []
    for vr in response.results:
        video = videos.find_by_id(vr.video_id)
        if video is None:
            continue
        if video.status == "missing" and not body.include_missing:
            continue
        moments = [
            MomentResponse(
                timestamp_sec=m.timestamp_sec,
                score=m.score,
                thumb_url=(
                    f"/api/videos/{vr.video_id}/thumbs/{m.frame_idx}"
                    if m.frame_idx is not None else None
                ),
                caption=m.caption,
                source="caption" if m.caption else "frame",
            )
            for m in vr.moments
        ]
        results.append(VideoResultResponse(
            video_id=vr.video_id,
            path=video.path,
            duration_sec=video.duration_sec,
            top_score=vr.top_score,
            moments=moments,
        ))

    return SearchApiResponse(query=body.query, results=results)
