from __future__ import annotations

from .db import Database
from .schemas import LibraryFolderRow
from .videos import _sql_literal


class LibraryFoldersRepo:
    def __init__(self, db: Database):
        self._table = db.table("library_folders")

    def insert(self, folder: LibraryFolderRow) -> None:
        self._table.add([folder.model_dump()])

    def list_all(self) -> list[LibraryFolderRow]:
        results = self._table.search().to_list()
        return [LibraryFolderRow(**r) for r in results]

    def find_by_id(self, id_: str) -> LibraryFolderRow | None:
        results = (
            self._table.search()
            .where(f"id = {_sql_literal(id_)}")
            .limit(1)
            .to_list()
        )
        return LibraryFolderRow(**results[0]) if results else None

    def delete(self, id_: str) -> None:
        self._table.delete(f"id = {_sql_literal(id_)}")
