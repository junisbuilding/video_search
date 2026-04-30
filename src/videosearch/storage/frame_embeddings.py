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
        return [FrameEmbeddingRow(**{k: v for k, v in r.items() if not k.startswith("_")}) for r in results]

    def find_nearest(self, video_id: str, timestamp_sec: float) -> FrameEmbeddingRow | None:
        rows = self.list_for_video(video_id)
        if not rows:
            return None
        return min(rows, key=lambda r: abs(r.timestamp_sec - timestamp_sec))

    def delete_for_video(self, video_id: str) -> None:
        self._table.delete(f"video_id = {_sql_literal(video_id)}")
