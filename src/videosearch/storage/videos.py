from __future__ import annotations

from typing import Any

from .db import Database
from .schemas import VideoRow


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


class VideosRepo:
    def __init__(self, db: Database):
        self._table = db.table("videos")

    def insert(self, video: VideoRow) -> None:
        self._table.add([video.model_dump()])

    def find_by_hash(self, hash_: str) -> VideoRow | None:
        results = (
            self._table.search()
            .where(f"hash = {_sql_literal(hash_)}")
            .limit(1)
            .to_list()
        )
        return VideoRow(**results[0]) if results else None

    def find_by_id(self, id_: str) -> VideoRow | None:
        results = (
            self._table.search()
            .where(f"id = {_sql_literal(id_)}")
            .limit(1)
            .to_list()
        )
        return VideoRow(**results[0]) if results else None

    def find_by_path(self, path: str) -> VideoRow | None:
        results = (
            self._table.search()
            .where(f"path = {_sql_literal(path)}")
            .limit(1)
            .to_list()
        )
        return VideoRow(**results[0]) if results else None

    def update(self, id_: str, **fields: Any) -> None:
        if not fields:
            return
        self._table.update(where=f"id = {_sql_literal(id_)}", values=fields)

    def list_by_status(self, status: str) -> list[VideoRow]:
        results = self._table.search().where(f"status = {_sql_literal(status)}").to_list()
        return [VideoRow(**r) for r in results]

    def list_by_folder(self, folder_id: str | None) -> list[VideoRow]:
        if folder_id is None:
            results = (
                self._table.search()
                .where("library_folder_id IS NULL")
                .to_list()
            )
        else:
            results = (
                self._table.search()
                .where(f"library_folder_id = {_sql_literal(folder_id)}")
                .to_list()
            )
        return [VideoRow(**r) for r in results]
