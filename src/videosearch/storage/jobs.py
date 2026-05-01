from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id                TEXT PRIMARY KEY,
    video_id          TEXT,
    path              TEXT,
    library_folder_id TEXT,
    kind              TEXT NOT NULL,
    status            TEXT NOT NULL,
    progress          REAL NOT NULL DEFAULT 0.0,
    error             TEXT,
    created_at        REAL NOT NULL,
    updated_at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at);
"""


@dataclass(frozen=True)
class Job:
    id: str
    video_id: str | None
    path: str | None
    library_folder_id: str | None
    kind: str
    status: str  # pending | in_progress | completed | failed
    progress: float
    error: str | None
    created_at: float
    updated_at: float


class JobsQueue:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def enqueue(
        self,
        *,
        kind: str,
        path: str | None = None,
        video_id: str | None = None,
        library_folder_id: str | None = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        now = time.time()
        self._conn.execute(
            "INSERT INTO jobs (id, video_id, path, library_folder_id, kind, status, "
            "progress, error, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', 0.0, NULL, ?, ?)",
            (job_id, video_id, path, library_folder_id, kind, now, now),
        )
        self._conn.commit()
        return job_id

    def claim(self) -> Job | None:
        cur = self._conn.execute(
            "SELECT * FROM jobs WHERE status = 'pending' "
            "ORDER BY created_at ASC LIMIT 1"
        )
        row = cur.fetchone()
        if row is None:
            return None
        now = time.time()
        self._conn.execute(
            "UPDATE jobs SET status = 'in_progress', updated_at = ? "
            "WHERE id = ? AND status = 'pending'",
            (now, row["id"]),
        )
        self._conn.commit()
        return Job(**{**dict(row), "status": "in_progress", "updated_at": now})

    def update_progress(self, job_id: str, progress: float) -> None:
        self._conn.execute(
            "UPDATE jobs SET progress = ?, updated_at = ? WHERE id = ?",
            (progress, time.time(), job_id),
        )
        self._conn.commit()

    def update_video_id(self, job_id: str, video_id: str) -> None:
        self._conn.execute(
            "UPDATE jobs SET video_id = ?, updated_at = ? WHERE id = ?",
            (video_id, time.time(), job_id),
        )
        self._conn.commit()

    def complete(self, job_id: str) -> None:
        self._conn.execute(
            "UPDATE jobs SET status = 'completed', progress = 1.0, "
            "updated_at = ? WHERE id = ?",
            (time.time(), job_id),
        )
        self._conn.commit()

    def fail(self, job_id: str, *, error: str) -> None:
        self._conn.execute(
            "UPDATE jobs SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
            (error, time.time(), job_id),
        )
        self._conn.commit()

    def get_by_id(self, job_id: str) -> Job | None:
        cur = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cur.fetchone()
        return Job(**dict(row)) if row else None

    def list_recent(self, limit: int = 200) -> list[Job]:
        cur = self._conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [Job(**dict(r)) for r in cur.fetchall()]

    def list_by_status(self, status: str) -> list[Job]:
        cur = self._conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC", (status,)
        )
        return [Job(**dict(r)) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
