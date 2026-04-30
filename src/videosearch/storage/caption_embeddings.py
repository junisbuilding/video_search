from __future__ import annotations

from collections.abc import Iterable

from .db import Database
from .schemas import CaptionEmbeddingRow
from .videos import _sql_literal


class CaptionEmbeddingsRepo:
    def __init__(self, db: Database):
        self._table = db.table("caption_embeddings")

    def insert_many(self, rows: Iterable[CaptionEmbeddingRow]) -> None:
        records = [r.model_dump() for r in rows]
        if records:
            self._table.add(records)

    def list_for_video(self, video_id: str) -> list[CaptionEmbeddingRow]:
        results = self._table.search().where(f"video_id = {_sql_literal(video_id)}").to_list()
        return [CaptionEmbeddingRow(**r) for r in results]

    def search(self, query_vector: list[float], limit: int) -> list[CaptionEmbeddingRow]:
        results = self._table.search(query_vector).limit(limit).to_list()
        return [CaptionEmbeddingRow(**{k: v for k, v in r.items() if not k.startswith("_")}) for r in results]

    def delete_for_video(self, video_id: str) -> None:
        self._table.delete(f"video_id = {_sql_literal(video_id)}")
