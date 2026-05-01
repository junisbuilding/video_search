from __future__ import annotations

from collections.abc import Iterable

from .db import Database
from .schemas import FrameEmbeddingRow
from .videos import _sql_literal


class FrameEmbeddingsRepo:
    def __init__(self, db: Database):
        self._table = db.table("frame_embeddings")

    def insert_many(self, rows: Iterable[FrameEmbeddingRow]) -> None:
        records = [r.model_dump() for r in rows]
        if records:
            self._table.add(records)

    def list_for_video(self, video_id: str) -> list[FrameEmbeddingRow]:
        results = self._table.search().where(f"video_id = {_sql_literal(video_id)}").to_list()
        return [FrameEmbeddingRow(**r) for r in results]

    def search(self, query_vector: list[float], limit: int) -> list[FrameEmbeddingRow]:
        results = self._table.search(query_vector).limit(limit).to_list()
        # LanceDB ANN search appends _distance; strip all private keys before Pydantic construction.
        return [FrameEmbeddingRow(**{k: v for k, v in r.items() if not k.startswith("_")}) for r in results]

    def find_nearest(self, video_id: str, timestamp_sec: float) -> FrameEmbeddingRow | None:
        """Return the frame closest in time to timestamp_sec. None if video has no frames.

        Tie-breaking between equidistant frames is arbitrary (storage retrieval order).
        """
        rows = self.list_for_video(video_id)
        if not rows:
            return None
        return min(rows, key=lambda r: abs(r.timestamp_sec - timestamp_sec))

    def find_frame(self, video_id: str, frame_idx: int) -> FrameEmbeddingRow | None:
        results = (
            self._table.search()
            .where(f"video_id = {_sql_literal(video_id)} AND frame_idx = {_sql_literal(frame_idx)}")
            .limit(1)
            .to_list()
        )
        if not results:
            return None
        return FrameEmbeddingRow(**{k: v for k, v in results[0].items() if not k.startswith("_")})

    def delete_for_video(self, video_id: str) -> None:
        self._table.delete(f"video_id = {_sql_literal(video_id)}")
