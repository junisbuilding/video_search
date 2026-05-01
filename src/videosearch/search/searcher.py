from __future__ import annotations

from videosearch.models.protocols import ImageEmbedder, TextEmbedder
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo

from .models import Moment, SearchResponse, VideoResult
from .rrf import rrf_fuse


class Searcher:
    def __init__(
        self,
        *,
        frames: FrameEmbeddingsRepo,
        captions: CaptionEmbeddingsRepo,
        image_embedder: ImageEmbedder,
        text_embedder: TextEmbedder,
    ) -> None:
        self._frames = frames
        self._captions = captions
        self._image_embedder = image_embedder
        self._text_embedder = text_embedder

    def search(self, query: str, *, k: int = 10) -> SearchResponse:
        frame_vec = self._image_embedder.embed_text(query)
        caption_vec = self._text_embedder.embed_text([query])[0]

        frame_hits = self._frames.search(frame_vec, limit=k * 5)
        caption_hits = self._captions.search(caption_vec, limit=k * 5)

        frame_by_id = {f"f:{r.video_id}:{r.frame_idx}": r for r in frame_hits}
        caption_by_id = {f"c:{r.video_id}:{r.scene_idx}": r for r in caption_hits}

        fused = rrf_fuse([list(frame_by_id), list(caption_by_id)])

        # Pre-fetch frames for all videos with caption hits to avoid one DB read per caption.
        caption_video_ids = {r.video_id for r in caption_hits}
        frames_by_video = {vid: self._frames.list_for_video(vid) for vid in caption_video_ids}

        moments_by_video: dict[str, list[Moment]] = {}
        for composite_id, score in fused:
            if composite_id.startswith("f:"):
                row = frame_by_id[composite_id]
                video_id = row.video_id
                moment = Moment(
                    timestamp_sec=row.timestamp_sec,
                    score=score,
                    thumb_path=row.thumb_path,
                )
            else:
                row = caption_by_id[composite_id]
                video_id = row.video_id
                frames = frames_by_video.get(video_id, [])
                nearest = min(frames, key=lambda f: abs(f.timestamp_sec - row.start_sec), default=None)
                moment = Moment(
                    timestamp_sec=row.start_sec,
                    score=score,
                    thumb_path=nearest.thumb_path if nearest else None,
                    caption=row.caption,
                )
            moments_by_video.setdefault(video_id, []).append(moment)

        results: list[VideoResult] = []
        for video_id, moments in moments_by_video.items():
            moments_sorted = sorted(moments, key=lambda m: m.score, reverse=True)
            results.append(VideoResult(
                video_id=video_id,
                top_score=moments_sorted[0].score,
                moments=tuple(moments_sorted),
            ))

        results.sort(key=lambda r: r.top_score, reverse=True)
        # k caps the number of VideoResult objects returned; moments per video are uncapped.
        return SearchResponse(query=query, results=tuple(results[:k]))
