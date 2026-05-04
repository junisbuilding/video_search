from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from videosearch.storage.db import Database


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


class DownloadStateRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, model_type: str, model_id: str, total_bytes: int) -> None:
        now = time.time()
        download_id = f"{model_type}:{model_id}"
        table = self._db.table("downloads")
        table.add([{
            "id": download_id,
            "model_type": model_type,
            "model_id": model_id,
            "downloaded_bytes": 0,
            "total_bytes": total_bytes,
            "status": "queued",
            "error_message": None,
            "updated_at": now,
            "created_at": now,
        }])

    def get_active(self) -> list[dict]:
        table = self._db.table("downloads")
        return table.search().where("status != 'complete' AND status != 'error'").to_list()

    def update_progress(self, download_id: str, downloaded_bytes: int, total_bytes: int) -> None:
        now = time.time()
        table = self._db.table("downloads")
        table.update(where=f"id = {_sql_literal(download_id)}", values={
            "downloaded_bytes": downloaded_bytes,
            "total_bytes": total_bytes,
            "status": "downloading",
            "updated_at": now,
        })

    def mark_complete(self, download_id: str) -> None:
        now = time.time()
        table = self._db.table("downloads")
        table.update(where=f"id = {_sql_literal(download_id)}", values={
            "status": "complete",
            "updated_at": now,
        })

    def mark_error(self, download_id: str, error_message: str) -> None:
        now = time.time()
        table = self._db.table("downloads")
        table.update(where=f"id = {_sql_literal(download_id)}", values={
            "status": "error",
            "error_message": error_message,
            "updated_at": now,
        })

    def cleanup_completed(self) -> None:
        """Delete completed or error records older than 1 hour."""
        one_hour_ago = time.time() - 3600
        table = self._db.table("downloads")
        table.delete(f"status = 'complete' OR status = 'error'")
