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

    def delete_for_video(self, video_id: str) -> None:
        self._table.delete(f"video_id = {_sql_literal(video_id)}")
