from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Moment:
    timestamp_sec: float
    score: float
    thumb_path: str | None
    caption: str | None = None


@dataclass(frozen=True)
class VideoResult:
    video_id: str
    top_score: float
    moments: tuple[Moment, ...]


@dataclass(frozen=True)
class SearchResponse:
    query: str
    results: tuple[VideoResult, ...]
