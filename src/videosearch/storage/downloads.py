from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from videosearch.storage.db import Database


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
