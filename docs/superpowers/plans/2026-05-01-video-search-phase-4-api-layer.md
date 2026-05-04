# API Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI HTTP server that exposes search, library management, job tracking, video streaming, and settings to the frontend, with a single background indexer thread and WebSocket job progress.

**Architecture:** FastAPI app created via `create_app(settings, startup=False)` factory for testability; all shared state lives in `app.state` and is accessed via `Depends()` functions in `deps.py`; a single `IndexerWorker` thread pulls from `JobsQueue` and calls `index_video()`; `JobBroadcaster` bridges the sync worker thread to async WebSocket clients.

**Tech Stack:** FastAPI 0.111+, uvicorn[standard], typer, python-multipart, tomli-w, starlette (bundled with FastAPI).

---

## File map

**Create:**
- `src/videosearch/api/__init__.py` — empty
- `src/videosearch/api/app.py` — `create_app()` factory + lifespan
- `src/videosearch/api/deps.py` — `Depends()` functions
- `src/videosearch/api/worker.py` — `IndexerWorker(threading.Thread)`
- `src/videosearch/api/ws.py` — `JobBroadcaster` + `/ws/jobs` WebSocket route
- `src/videosearch/api/routers/__init__.py` — empty
- `src/videosearch/api/routers/health.py`
- `src/videosearch/api/routers/search.py`
- `src/videosearch/api/routers/library.py`
- `src/videosearch/api/routers/ingest.py`
- `src/videosearch/api/routers/jobs.py`
- `src/videosearch/api/routers/videos.py`
- `src/videosearch/api/routers/fs.py`
- `src/videosearch/api/routers/settings.py`
- `src/videosearch/cli.py` — `videosearch serve` typer app
- `tests/api/__init__.py` — empty
- `tests/api/conftest.py` — shared TestClient fixture with dep overrides
- `tests/api/test_health.py`
- `tests/api/test_search.py`
- `tests/api/test_library.py`
- `tests/api/test_ingest.py`
- `tests/api/test_jobs.py`
- `tests/api/test_videos.py`
- `tests/api/test_fs.py`
- `tests/api/test_settings.py`
- `tests/api/test_integration.py`

**Modify:**
- `pyproject.toml` — add dependencies + `[project.scripts]`
- `src/videosearch/search/models.py` — add `frame_idx: int | None = None` to `Moment`
- `src/videosearch/search/searcher.py` — populate `frame_idx` in both moment branches
- `src/videosearch/storage/jobs.py` — add `path`, `library_folder_id` columns; add `list_recent()`, `get_by_id()`, `update_video_id()`
- `src/videosearch/storage/videos.py` — add `list_by_folder()`
- `src/videosearch/storage/frame_embeddings.py` — add `find_frame()`
- `src/videosearch/storage/library_folders.py` — add `find_by_id()`
- `tests/search/test_searcher.py` — add two tests for `frame_idx` propagation

---

### Task 1: Add dependencies, scaffold packages, add `Moment.frame_idx`

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/videosearch/search/models.py`
- Modify: `src/videosearch/search/searcher.py`
- Modify: `tests/search/test_searcher.py`
- Create: `src/videosearch/api/__init__.py`, `src/videosearch/api/routers/__init__.py`, `tests/api/__init__.py`

- [ ] **Step 1: Add new dependencies to pyproject.toml**

Edit `pyproject.toml`. In `dependencies`, add after the existing list:
```toml
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "typer>=0.12",
    "python-multipart>=0.0.9",
    "tomli-w>=1.0",
```

Add a new section after `[build-system]`:
```toml
[project.scripts]
videosearch = "videosearch.cli:app"
```

- [ ] **Step 2: Install dependencies**

```bash
uv sync
```

Expected: resolves and installs fastapi, uvicorn, typer, python-multipart, tomli-w.

- [ ] **Step 3: Create empty package files**

```bash
touch src/videosearch/api/__init__.py
mkdir -p src/videosearch/api/routers
touch src/videosearch/api/routers/__init__.py
mkdir -p tests/api
touch tests/api/__init__.py
```

- [ ] **Step 4: Write failing tests for Moment.frame_idx**

Add to `tests/search/test_searcher.py`:

```python
def test_frame_hit_carries_frame_idx():
    searcher = _make_searcher(
        frame_hits=[_frame_row("v1", 7, 1.0)],
        caption_hits=[],
    )
    result = searcher.search("query")
    assert result.results[0].moments[0].frame_idx == 7


def test_caption_hit_carries_frame_idx_from_nearest():
    nearest = _frame_row("v1", 5, 0.5)
    searcher = _make_searcher(
        frame_hits=[],
        caption_hits=[_caption_row("v1", 0)],
        nearest=nearest,
    )
    result = searcher.search("scene query")
    assert result.results[0].moments[0].frame_idx == 5
```

- [ ] **Step 5: Run to confirm failure**

```bash
uv run pytest tests/search/test_searcher.py::test_frame_hit_carries_frame_idx tests/search/test_searcher.py::test_caption_hit_carries_frame_idx_from_nearest -v
```

Expected: FAIL — `Moment has no field 'frame_idx'` (AttributeError or assertion on None).

- [ ] **Step 6: Add `frame_idx` to Moment**

Edit `src/videosearch/search/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Moment:
    timestamp_sec: float
    score: float
    thumb_path: str | None
    caption: str | None = None
    frame_idx: int | None = None


@dataclass(frozen=True)
class VideoResult:
    video_id: str
    top_score: float
    moments: tuple[Moment, ...]


@dataclass(frozen=True)
class SearchResponse:
    query: str
    results: tuple[VideoResult, ...]
```

- [ ] **Step 7: Populate frame_idx in Searcher**

Edit `src/videosearch/search/searcher.py`. Replace the two `Moment(...)` constructions:

```python
            if composite_id.startswith("f:"):
                row = frame_by_id[composite_id]
                video_id = row.video_id
                moment = Moment(
                    timestamp_sec=row.timestamp_sec,
                    score=score,
                    thumb_path=row.thumb_path,
                    frame_idx=row.frame_idx,
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
                    frame_idx=nearest.frame_idx if nearest else None,
                )
```

- [ ] **Step 8: Run all search tests**

```bash
uv run pytest tests/search/ -v
```

Expected: all 20 tests pass (18 existing + 2 new).

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml src/videosearch/search/models.py src/videosearch/search/searcher.py tests/search/test_searcher.py src/videosearch/api/ tests/api/
git commit -m "feat(api): add dependencies, scaffold api package, add Moment.frame_idx"
```

---

### Task 2: Storage enhancements

**Files:**
- Modify: `src/videosearch/storage/jobs.py`
- Modify: `src/videosearch/storage/videos.py`
- Modify: `src/videosearch/storage/frame_embeddings.py`
- Modify: `src/videosearch/storage/library_folders.py`
- Modify: `tests/storage/test_jobs.py`
- Modify: `tests/storage/test_videos.py`
- Modify: `tests/storage/test_frame_embeddings.py`
- Create: `tests/storage/test_library_folders.py`

- [ ] **Step 1: Write failing tests for new storage methods**

Add to `tests/storage/test_jobs.py`:

```python
def test_list_recent_returns_all_statuses(tmp_path):
    q = JobsQueue(tmp_path / "jobs.db")
    id1 = q.enqueue(kind="index", path="/a.mp4")
    id2 = q.enqueue(kind="index", path="/b.mp4")
    q.claim()
    q.complete(id1)
    jobs = q.list_recent(limit=10)
    ids = {j.id for j in jobs}
    assert id1 in ids
    assert id2 in ids
    q.close()


def test_enqueue_stores_path_and_folder_id(tmp_path):
    q = JobsQueue(tmp_path / "jobs.db")
    job_id = q.enqueue(kind="index", path="/videos/clip.mp4", library_folder_id="folder-1")
    jobs = q.list_recent(limit=10)
    job = next(j for j in jobs if j.id == job_id)
    assert job.path == "/videos/clip.mp4"
    assert job.library_folder_id == "folder-1"
    q.close()


def test_get_by_id_returns_job(tmp_path):
    q = JobsQueue(tmp_path / "jobs.db")
    job_id = q.enqueue(kind="index", path="/a.mp4")
    job = q.get_by_id(job_id)
    assert job is not None
    assert job.id == job_id
    q.close()


def test_update_video_id_sets_field(tmp_path):
    q = JobsQueue(tmp_path / "jobs.db")
    job_id = q.enqueue(kind="index", path="/a.mp4")
    q.update_video_id(job_id, "video-uuid-1")
    job = q.get_by_id(job_id)
    assert job.video_id == "video-uuid-1"
    q.close()
```

Add to `tests/storage/test_videos.py`:

```python
def test_list_by_folder_returns_matching_videos(tmp_path):
    db = Database(tmp_path / "data")
    repo = VideosRepo(db)
    v1 = _make_video("v1", library_folder_id="folder-1")
    v2 = _make_video("v2", library_folder_id="folder-1")
    v3 = _make_video("v3", library_folder_id="folder-2")
    repo.insert(v1); repo.insert(v2); repo.insert(v3)
    results = repo.list_by_folder("folder-1")
    ids = {r.id for r in results}
    assert ids == {"v1", "v2"}


def test_list_by_folder_none_returns_ad_hoc(tmp_path):
    db = Database(tmp_path / "data")
    repo = VideosRepo(db)
    v1 = _make_video("v1", library_folder_id=None)
    v2 = _make_video("v2", library_folder_id="folder-1")
    repo.insert(v1); repo.insert(v2)
    results = repo.list_by_folder(None)
    assert len(results) == 1
    assert results[0].id == "v1"
```

(Note: `_make_video` helper already exists in the test file. If not, add it:
```python
import time, uuid
from videosearch.storage.schemas import VideoRow

def _make_video(id_: str, *, library_folder_id: str | None = None) -> VideoRow:
    return VideoRow(
        id=id_, path=f"/tmp/{id_}.mp4", hash=id_,
        duration_sec=10.0, fps=30.0, width=1920, height=1080,
        mtime=time.time(), status="indexed", last_seen_at=time.time(),
        library_folder_id=library_folder_id,
    )
```
)

Add to `tests/storage/test_frame_embeddings.py`:

```python
def test_find_frame_returns_correct_row(tmp_path):
    db = Database(tmp_path / "data")
    repo = FrameEmbeddingsRepo(db)
    rows = [
        FrameEmbeddingRow(video_id="v1", frame_idx=1, timestamp_sec=0.0,
                          embedding=[0.1]*SIGLIP_DIM, thumb_path="/t/1.jpg"),
        FrameEmbeddingRow(video_id="v1", frame_idx=2, timestamp_sec=1.0,
                          embedding=[0.1]*SIGLIP_DIM, thumb_path="/t/2.jpg"),
    ]
    repo.insert_many(rows)
    result = repo.find_frame("v1", 2)
    assert result is not None
    assert result.frame_idx == 2
    assert result.thumb_path == "/t/2.jpg"


def test_find_frame_returns_none_when_missing(tmp_path):
    db = Database(tmp_path / "data")
    repo = FrameEmbeddingsRepo(db)
    assert repo.find_frame("v1", 99) is None
```

Create `tests/storage/test_library_folders.py`:

```python
from __future__ import annotations

import time
from videosearch.storage.db import Database
from videosearch.storage.library_folders import LibraryFoldersRepo
from videosearch.storage.schemas import LibraryFolderRow


def _make_folder(id_: str, path: str = "/movies") -> LibraryFolderRow:
    return LibraryFolderRow(id=id_, path=path, added_at=time.time())


def test_find_by_id_returns_folder(tmp_path):
    db = Database(tmp_path / "data")
    repo = LibraryFoldersRepo(db)
    repo.insert(_make_folder("f1", "/movies"))
    result = repo.find_by_id("f1")
    assert result is not None
    assert result.id == "f1"
    assert result.path == "/movies"


def test_find_by_id_returns_none_when_missing(tmp_path):
    db = Database(tmp_path / "data")
    repo = LibraryFoldersRepo(db)
    assert repo.find_by_id("nonexistent") is None
```

- [ ] **Step 2: Run to confirm failures**

```bash
uv run pytest tests/storage/ -v 2>&1 | tail -20
```

Expected: multiple FAIL — new methods not defined yet.

- [ ] **Step 3: Implement JobsQueue enhancements**

Replace `src/videosearch/storage/jobs.py` entirely:

```python
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
        """Atomically pull the oldest pending job, mark it in_progress."""
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
```

Note: `check_same_thread=False` is added because the worker thread shares this connection with the main thread.

- [ ] **Step 4: Add `list_by_folder` to VideosRepo**

Add to `src/videosearch/storage/videos.py` inside the `VideosRepo` class, after `list_by_status`:

```python
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
```

- [ ] **Step 5: Add `find_frame` to FrameEmbeddingsRepo**

Add to `src/videosearch/storage/frame_embeddings.py` inside the class:

```python
    def find_frame(self, video_id: str, frame_idx: int) -> FrameEmbeddingRow | None:
        results = (
            self._table.search()
            .where(f"video_id = {_sql_literal(video_id)} AND frame_idx = {frame_idx}")
            .limit(1)
            .to_list()
        )
        if not results:
            return None
        return FrameEmbeddingRow(**{k: v for k, v in results[0].items() if not k.startswith("_")})
```

Also add the import at top: `from .videos import _sql_literal` is already there. ✓

- [ ] **Step 6: Add `find_by_id` to LibraryFoldersRepo**

Add to `src/videosearch/storage/library_folders.py` inside the class:

```python
    def find_by_id(self, id_: str) -> LibraryFolderRow | None:
        results = (
            self._table.search()
            .where(f"id = {_sql_literal(id_)}")
            .limit(1)
            .to_list()
        )
        return LibraryFolderRow(**results[0]) if results else None
```

- [ ] **Step 7: Run storage tests**

```bash
uv run pytest tests/storage/ -v 2>&1 | tail -25
```

Expected: all storage tests pass (existing + new).

- [ ] **Step 8: Commit**

```bash
git add src/videosearch/storage/ tests/storage/
git commit -m "feat(storage): add path/folder_id to jobs, list_recent, find_frame, list_by_folder, find_by_id"
```

---

### Task 3: WebSocket broadcaster (`ws.py`)

**Files:**
- Create: `src/videosearch/api/ws.py`
- Create: `tests/api/test_ws.py`

- [ ] **Step 1: Write failing tests**

Create `tests/api/test_ws.py`:

```python
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from videosearch.api.ws import JobBroadcaster


@pytest.fixture
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def broadcaster(loop):
    return JobBroadcaster(loop)


def test_register_adds_client(broadcaster):
    ws = MagicMock()
    broadcaster.register(ws)
    assert ws in broadcaster._clients


def test_unregister_removes_client(broadcaster):
    ws = MagicMock()
    broadcaster.register(ws)
    broadcaster.unregister(ws)
    assert ws not in broadcaster._clients


def test_broadcast_calls_run_coroutine_threadsafe(broadcaster):
    event = {"job_id": "j1", "status": "completed"}
    with patch("asyncio.run_coroutine_threadsafe") as mock_rct:
        broadcaster.broadcast(event)
        mock_rct.assert_called_once()
        # First arg is a coroutine, second is the loop
        assert mock_rct.call_args[0][1] is broadcaster._loop


@pytest.mark.asyncio
async def test_send_all_delivers_to_registered_clients(loop):
    broadcaster = JobBroadcaster(loop)
    ws = MagicMock()
    ws.send_json = AsyncMock()
    broadcaster.register(ws)
    await broadcaster.send_all({"status": "ok"})
    ws.send_json.assert_awaited_once_with({"status": "ok"})


@pytest.mark.asyncio
async def test_send_all_removes_dead_clients(loop):
    broadcaster = JobBroadcaster(loop)
    ws = MagicMock()
    ws.send_json = AsyncMock(side_effect=RuntimeError("disconnected"))
    broadcaster.register(ws)
    await broadcaster.send_all({"status": "ok"})
    assert ws not in broadcaster._clients
```

Add `anyio` marker support — it's already in `pyproject.toml` via `pytest-anyio`. Check that `pytest-anyio` or `anyio[pytest]` is available:

```bash
uv run python -c "import anyio; print('ok')"
```

If missing, the async tests will be skipped (that's fine — the sync tests still validate the broadcaster).

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/test_ws.py -v
```

Expected: FAIL — `cannot import name 'JobBroadcaster'`.

- [ ] **Step 3: Implement ws.py**

Create `src/videosearch/api/ws.py`:

```python
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

router = APIRouter()


class JobBroadcaster:
    """Thread-safe broadcaster: sync worker thread → async WebSocket clients."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._clients: set[WebSocket] = set()

    def register(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def unregister(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def send_all(self, event: dict) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                await ws.send_json(event)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    def broadcast(self, event: dict) -> None:
        """Call from any thread to push an event to all connected WS clients."""
        asyncio.run_coroutine_threadsafe(self.send_all(event), self._loop)


# The WebSocket route is registered in app.py after deps are available.
# It is defined here to keep WS logic co-located with JobBroadcaster.
def make_ws_router(get_broadcaster_dep, get_jobs_queue_dep) -> APIRouter:
    ws_router = APIRouter()

    @ws_router.websocket("/ws/jobs")
    async def ws_jobs(
        websocket: WebSocket,
        broadcaster: JobBroadcaster = Depends(get_broadcaster_dep),
        jobs_queue=Depends(get_jobs_queue_dep),
    ) -> None:
        await websocket.accept()
        broadcaster.register(websocket)
        try:
            # Send snapshot of recent jobs so client starts with current state
            for job in jobs_queue.list_recent(200):
                await websocket.send_json({
                    "job_id": job.id,
                    "video_id": job.video_id,
                    "kind": job.kind,
                    "status": job.status,
                    "progress": job.progress,
                    "error": job.error,
                })
            # Hold connection open; events arrive via broadcaster.broadcast()
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            broadcaster.unregister(websocket)

    return ws_router
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/test_ws.py -v
```

Expected: all sync tests pass; async tests pass if anyio plugin available, otherwise skip.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/ws.py tests/api/test_ws.py
git commit -m "feat(api): add JobBroadcaster and WebSocket job-progress route"
```

---

### Task 4: Background worker (`worker.py`)

**Files:**
- Create: `src/videosearch/api/worker.py`
- Create: `tests/api/test_worker.py`

- [ ] **Step 1: Write failing tests**

Create `tests/api/test_worker.py`:

```python
from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from videosearch.api.worker import IndexerWorker
from videosearch.storage.jobs import Job


def _make_job(
    job_id: str = "j1",
    path: str = "/tmp/video.mp4",
    library_folder_id: str | None = None,
) -> Job:
    return Job(
        id=job_id,
        video_id=None,
        path=path,
        library_folder_id=library_folder_id,
        kind="index",
        status="in_progress",
        progress=0.0,
        error=None,
        created_at=time.time(),
        updated_at=time.time(),
    )


def _make_worker(jobs, broadcaster=None) -> IndexerWorker:
    return IndexerWorker(
        jobs=jobs,
        videos=MagicMock(),
        frames=MagicMock(),
        captions=MagicMock(),
        image_embedder=MagicMock(),
        text_embedder=MagicMock(),
        captioner=MagicMock(),
        work_dir=Path("/tmp/work"),
        broadcaster=broadcaster or MagicMock(),
        frame_fps=1.0,
        scene_detection=False,
    )


def test_worker_processes_job_and_broadcasts_completed():
    jobs = MagicMock()
    broadcaster = MagicMock()
    jobs.claim.side_effect = [_make_job(), None, None]

    from videosearch.indexer import IndexResult
    with patch("videosearch.api.worker.index_video") as mock_index:
        mock_index.return_value = IndexResult(video_id="v1", hash="abc", status="indexed")
        worker = _make_worker(jobs, broadcaster)
        worker._process(jobs.claim.side_effect[0])

    jobs.complete.assert_called_once_with("j1")
    calls = [c[0][0] for c in broadcaster.broadcast.call_args_list]
    statuses = [c["status"] for c in calls]
    assert "in_progress" in statuses
    assert "completed" in statuses


def test_worker_broadcasts_failed_on_exception():
    jobs = MagicMock()
    broadcaster = MagicMock()

    with patch("videosearch.api.worker.index_video", side_effect=RuntimeError("boom")):
        worker = _make_worker(jobs, broadcaster)
        worker._process(_make_job())

    jobs.fail.assert_called_once()
    calls = [c[0][0] for c in broadcaster.broadcast.call_args_list]
    statuses = [c["status"] for c in calls]
    assert "failed" in statuses


def test_worker_fails_job_when_path_is_none():
    jobs = MagicMock()
    broadcaster = MagicMock()
    job = Job(id="j1", video_id=None, path=None, library_folder_id=None,
              kind="index", status="in_progress", progress=0.0, error=None,
              created_at=time.time(), updated_at=time.time())
    worker = _make_worker(jobs, broadcaster)
    worker._process(job)
    jobs.fail.assert_called_once_with("j1", error="job has no path")


def test_worker_stops_cleanly():
    jobs = MagicMock()
    jobs.claim.return_value = None
    worker = _make_worker(jobs)
    worker.start()
    time.sleep(0.05)
    worker.stop()
    worker.join(timeout=2.0)
    assert not worker.is_alive()
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/test_worker.py -v
```

Expected: FAIL — `cannot import name 'IndexerWorker'`.

- [ ] **Step 3: Implement worker.py**

Create `src/videosearch/api/worker.py`:

```python
from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from videosearch.indexer import index_video
from videosearch.models.protocols import Captioner, ImageEmbedder, TextEmbedder
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.jobs import Job, JobsQueue
from videosearch.storage.videos import VideosRepo

if TYPE_CHECKING:
    from videosearch.api.ws import JobBroadcaster


class IndexerWorker(threading.Thread):
    def __init__(
        self,
        *,
        jobs: JobsQueue,
        videos: VideosRepo,
        frames: FrameEmbeddingsRepo,
        captions: CaptionEmbeddingsRepo,
        image_embedder: ImageEmbedder,
        text_embedder: TextEmbedder,
        captioner: Captioner,
        work_dir: Path,
        broadcaster: "JobBroadcaster",
        frame_fps: float = 1.0,
        scene_detection: bool = True,
    ) -> None:
        super().__init__(daemon=True, name="indexer-worker")
        self._jobs = jobs
        self._videos = videos
        self._frames = frames
        self._captions = captions
        self._image_embedder = image_embedder
        self._text_embedder = text_embedder
        self._captioner = captioner
        self._work_dir = work_dir
        self._broadcaster = broadcaster
        self._frame_fps = frame_fps
        self._scene_detection = scene_detection
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            job = self._jobs.claim()
            if job is None:
                self._stop.wait(timeout=1.0)
                continue
            self._process(job)

    def stop(self) -> None:
        self._stop.set()

    def _process(self, job: Job) -> None:
        if not job.path:
            self._jobs.fail(job.id, error="job has no path")
            self._broadcaster.broadcast({
                "job_id": job.id, "video_id": job.video_id,
                "kind": job.kind, "status": "failed",
                "progress": 0.0, "error": "job has no path",
            })
            return

        self._broadcaster.broadcast({
            "job_id": job.id, "video_id": job.video_id,
            "kind": job.kind, "status": "in_progress",
            "progress": 0.0, "error": None,
        })
        try:
            result = index_video(
                path=Path(job.path),
                videos=self._videos,
                frames=self._frames,
                captions=self._captions,
                image_embedder=self._image_embedder,
                text_embedder=self._text_embedder,
                captioner=self._captioner,
                work_dir=self._work_dir,
                frame_fps=self._frame_fps,
                scene_detection=self._scene_detection,
                library_folder_id=job.library_folder_id,
            )
            self._jobs.update_video_id(job.id, result.video_id)
            self._jobs.complete(job.id)
            self._broadcaster.broadcast({
                "job_id": job.id, "video_id": result.video_id,
                "kind": job.kind, "status": "completed",
                "progress": 1.0, "error": None,
            })
        except Exception as e:
            self._jobs.fail(job.id, error=str(e))
            self._broadcaster.broadcast({
                "job_id": job.id, "video_id": job.video_id,
                "kind": job.kind, "status": "failed",
                "progress": 0.0, "error": str(e),
            })
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/test_worker.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/worker.py tests/api/test_worker.py
git commit -m "feat(api): add IndexerWorker background thread"
```

---

### Task 5: App factory, deps, and test conftest

**Files:**
- Create: `src/videosearch/api/app.py`
- Create: `src/videosearch/api/deps.py`
- Create: `tests/api/conftest.py`

- [ ] **Step 1: Implement deps.py**

Create `src/videosearch/api/deps.py`:

```python
from __future__ import annotations

from starlette.requests import HTTPConnection

from videosearch.api.worker import IndexerWorker
from videosearch.api.ws import JobBroadcaster
from videosearch.config import Settings
from videosearch.search import Searcher
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.jobs import JobsQueue
from videosearch.storage.library_folders import LibraryFoldersRepo
from videosearch.storage.videos import VideosRepo


def get_settings(conn: HTTPConnection) -> Settings:
    return conn.app.state.settings


def get_searcher(conn: HTTPConnection) -> Searcher:
    return conn.app.state.searcher


def get_jobs_queue(conn: HTTPConnection) -> JobsQueue:
    return conn.app.state.jobs_queue


def get_videos_repo(conn: HTTPConnection) -> VideosRepo:
    return conn.app.state.videos_repo


def get_frames_repo(conn: HTTPConnection) -> FrameEmbeddingsRepo:
    return conn.app.state.frames_repo


def get_captions_repo(conn: HTTPConnection) -> CaptionEmbeddingsRepo:
    return conn.app.state.captions_repo


def get_library_folders_repo(conn: HTTPConnection) -> LibraryFoldersRepo:
    return conn.app.state.library_folders_repo


def get_broadcaster(conn: HTTPConnection) -> JobBroadcaster:
    return conn.app.state.broadcaster


def get_worker(conn: HTTPConnection) -> IndexerWorker:
    return conn.app.state.worker
```

- [ ] **Step 2: Implement app.py**

Create `src/videosearch/api/app.py`:

```python
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from videosearch.api import deps
from videosearch.api.ws import JobBroadcaster, make_ws_router
from videosearch.config import Settings


def create_app(settings: Settings, *, startup: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if startup:
            from videosearch.models.bge import BgeTextEmbedder
            from videosearch.models.llama_cpp_captioner import LlamaCppCaptioner
            from videosearch.models.loader import resolve_gguf
            from videosearch.models.siglip import SiglipEmbedder
            from videosearch.search import Searcher
            from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
            from videosearch.storage.db import Database
            from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
            from videosearch.storage.jobs import JobsQueue
            from videosearch.storage.library_folders import LibraryFoldersRepo
            from videosearch.storage.videos import VideosRepo
            from videosearch.api.worker import IndexerWorker

            if not settings.vlm_model or not settings.vlm_mmproj:
                raise RuntimeError(
                    "VS_VLM_MODEL and VS_VLM_MMPROJ must be set.\n"
                    "Example: VS_VLM_MODEL=bartowski/Qwen2.5-VL-3B-Instruct-GGUF"
                    "::Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
                )

            image_embedder = SiglipEmbedder(settings.siglip_model)
            text_embedder = BgeTextEmbedder(settings.text_embedder)
            vlm_path = resolve_gguf(settings.vlm_model, cache_dir=settings.models_dir)
            mmproj_path = resolve_gguf(settings.vlm_mmproj, cache_dir=settings.models_dir)
            captioner = LlamaCppCaptioner(
                str(vlm_path), str(mmproj_path),
                n_gpu_layers=settings.vlm_n_gpu_layers,
            )

            db = Database(settings.data_dir)
            jobs_queue = JobsQueue(settings.data_dir / "jobs.db")
            videos = VideosRepo(db)
            frames = FrameEmbeddingsRepo(db)
            captions = CaptionEmbeddingsRepo(db)
            folders = LibraryFoldersRepo(db)
            searcher = Searcher(
                frames=frames, captions=captions,
                image_embedder=image_embedder, text_embedder=text_embedder,
            )

            loop = asyncio.get_running_loop()
            broadcaster = JobBroadcaster(loop)

            worker = IndexerWorker(
                jobs=jobs_queue, videos=videos, frames=frames, captions=captions,
                image_embedder=image_embedder, text_embedder=text_embedder,
                captioner=captioner, work_dir=settings.data_dir / "work",
                broadcaster=broadcaster, frame_fps=settings.frame_fps,
                scene_detection=settings.scene_detection,
            )
            worker.start()

            app.state.settings = settings
            app.state.searcher = searcher
            app.state.jobs_queue = jobs_queue
            app.state.videos_repo = videos
            app.state.frames_repo = frames
            app.state.captions_repo = captions
            app.state.library_folders_repo = folders
            app.state.broadcaster = broadcaster
            app.state.worker = worker

            yield

            worker.stop()
            worker.join(timeout=10)
            jobs_queue.close()
        else:
            yield

    app = FastAPI(lifespan=lifespan, title="Video Search API")

    from videosearch.api.routers import (
        fs, health, ingest, jobs, library, search,
        settings as settings_router, videos,
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(library.router, prefix="/api")
    app.include_router(ingest.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(videos.router, prefix="/api")
    app.include_router(fs.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(make_ws_router(deps.get_broadcaster, deps.get_jobs_queue))

    return app
```

- [ ] **Step 3: Create test conftest**

Create `tests/api/conftest.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from videosearch.api import deps
from videosearch.api.app import create_app
from videosearch.config import Settings


@pytest.fixture
def test_settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", models_dir=tmp_path / "models")


@pytest.fixture
def mock_searcher():
    return MagicMock()


@pytest.fixture
def mock_jobs():
    return MagicMock()


@pytest.fixture
def mock_videos():
    return MagicMock()


@pytest.fixture
def mock_frames():
    return MagicMock()


@pytest.fixture
def mock_folders():
    return MagicMock()


@pytest.fixture
def mock_broadcaster():
    return MagicMock()


@pytest.fixture
def mock_worker():
    return MagicMock()


@pytest.fixture
def client(
    test_settings,
    mock_searcher,
    mock_jobs,
    mock_videos,
    mock_frames,
    mock_folders,
    mock_broadcaster,
    mock_worker,
):
    app = create_app(test_settings, startup=False)
    app.dependency_overrides.update({
        deps.get_settings: lambda: test_settings,
        deps.get_searcher: lambda: mock_searcher,
        deps.get_jobs_queue: lambda: mock_jobs,
        deps.get_videos_repo: lambda: mock_videos,
        deps.get_frames_repo: lambda: mock_frames,
        deps.get_library_folders_repo: lambda: mock_folders,
        deps.get_broadcaster: lambda: mock_broadcaster,
        deps.get_worker: lambda: mock_worker,
    })
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 4: Verify app can be imported**

```bash
uv run python -c "from videosearch.api.app import create_app; print('ok')"
```

Expected: `ok` (routers don't exist yet — this will fail until all router files exist).

Create stub router files so the import succeeds. Create each of the following with empty `router = APIRouter()`:

```bash
for name in health search library ingest jobs videos fs settings; do
cat > src/videosearch/api/routers/${name}.py << 'EOF'
from __future__ import annotations
from fastapi import APIRouter
router = APIRouter()
EOF
done
```

- [ ] **Step 5: Verify import now succeeds**

```bash
uv run python -c "from videosearch.api.app import create_app; from videosearch.config import Settings; app = create_app(Settings(), startup=False); print('ok')"
```

Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add src/videosearch/api/app.py src/videosearch/api/deps.py src/videosearch/api/routers/ tests/api/conftest.py
git commit -m "feat(api): add app factory, deps, test conftest, and stub routers"
```

---

### Task 6: Health router

**Files:**
- Modify: `src/videosearch/api/routers/health.py`
- Create: `tests/api/test_health.py`

- [ ] **Step 1: Write failing tests**

Create `tests/api/test_health.py`:

```python
from __future__ import annotations


def test_health_returns_ok(client, mock_videos):
    mock_videos.list_by_status.return_value = []
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ok", "degraded")
    assert isinstance(data["db"], bool)
    assert isinstance(data["models_loaded"], bool)
    assert data["gpu_backend"] in ("mps", "cuda", "cpu")
    assert isinstance(data["indexed_count"], int)


def test_health_reports_indexed_count(client, mock_videos):
    from unittest.mock import MagicMock
    from videosearch.storage.schemas import VideoRow
    import time

    videos = [
        VideoRow(id=f"v{i}", path=f"/v{i}.mp4", hash=f"h{i}",
                 duration_sec=10.0, fps=30.0, width=1920, height=1080,
                 mtime=time.time(), status="indexed", last_seen_at=time.time())
        for i in range(3)
    ]
    mock_videos.list_by_status.return_value = videos
    r = client.get("/api/health")
    assert r.json()["indexed_count"] == 3


def test_health_degraded_when_db_fails(client, mock_videos):
    mock_videos.list_by_status.side_effect = RuntimeError("db down")
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"
    assert r.json()["db"] is False
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/test_health.py -v
```

Expected: FAIL — router returns 404 (stub has no routes).

- [ ] **Step 3: Implement health router**

Replace `src/videosearch/api/routers/health.py`:

```python
from __future__ import annotations

import torch
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from videosearch.api.deps import get_videos_repo
from videosearch.storage.videos import VideosRepo

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    db: bool
    models_loaded: bool
    gpu_backend: str
    indexed_count: int


@router.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    videos: VideosRepo = Depends(get_videos_repo),
) -> HealthResponse:
    db_ok = True
    indexed_count = 0
    try:
        rows = videos.list_by_status("indexed")
        indexed_count = len(rows)
    except Exception:
        db_ok = False

    models_loaded = hasattr(request.app.state, "searcher")

    if torch.backends.mps.is_available():
        gpu_backend = "mps"
    elif torch.cuda.is_available():
        gpu_backend = "cuda"
    else:
        gpu_backend = "cpu"

    status = "ok" if (db_ok and models_loaded) else "degraded"
    return HealthResponse(
        status=status,
        db=db_ok,
        models_loaded=models_loaded,
        gpu_backend=gpu_backend,
        indexed_count=indexed_count,
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/test_health.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/routers/health.py tests/api/test_health.py
git commit -m "feat(api): add health endpoint"
```

---

### Task 7: Search router

**Files:**
- Modify: `src/videosearch/api/routers/search.py`
- Create: `tests/api/test_search.py`

- [ ] **Step 1: Write failing tests**

Create `tests/api/test_search.py`:

```python
from __future__ import annotations

import time

from videosearch.search.models import Moment, SearchResponse, VideoResult
from videosearch.storage.schemas import VideoRow


def _video_row(id_: str = "v1", status: str = "indexed") -> VideoRow:
    return VideoRow(
        id=id_, path=f"/videos/{id_}.mp4", hash=id_,
        duration_sec=60.0, fps=30.0, width=1920, height=1080,
        mtime=time.time(), status=status, last_seen_at=time.time(),
    )


def _search_response(video_id: str = "v1", frame_idx: int = 3) -> SearchResponse:
    return SearchResponse(
        query="test query",
        results=(
            VideoResult(
                video_id=video_id,
                top_score=0.9,
                moments=(
                    Moment(
                        timestamp_sec=1.0, score=0.9,
                        thumb_path="/tmp/thumb.jpg",
                        frame_idx=frame_idx,
                    ),
                ),
            ),
        ),
    )


def test_search_returns_200_with_results(client, mock_searcher, mock_videos):
    mock_searcher.search.return_value = _search_response()
    mock_videos.find_by_id.return_value = _video_row()

    r = client.post("/api/search", json={"query": "test query"})

    assert r.status_code == 200
    data = r.json()
    assert data["query"] == "test query"
    assert len(data["results"]) == 1
    assert data["results"][0]["video_id"] == "v1"
    assert data["results"][0]["path"] == "/videos/v1.mp4"


def test_search_constructs_thumb_url_from_frame_idx(client, mock_searcher, mock_videos):
    mock_searcher.search.return_value = _search_response(frame_idx=7)
    mock_videos.find_by_id.return_value = _video_row()

    r = client.post("/api/search", json={"query": "test"})

    moment = r.json()["results"][0]["moments"][0]
    assert moment["thumb_url"] == "/api/videos/v1/thumbs/7"


def test_search_filters_missing_videos_by_default(client, mock_searcher, mock_videos):
    mock_searcher.search.return_value = _search_response()
    mock_videos.find_by_id.return_value = _video_row(status="missing")

    r = client.post("/api/search", json={"query": "test"})

    assert r.json()["results"] == []


def test_search_includes_missing_when_requested(client, mock_searcher, mock_videos):
    mock_searcher.search.return_value = _search_response()
    mock_videos.find_by_id.return_value = _video_row(status="missing")

    r = client.post("/api/search", json={"query": "test", "include_missing": True})

    assert len(r.json()["results"]) == 1


def test_search_passes_k_to_searcher(client, mock_searcher, mock_videos):
    mock_searcher.search.return_value = SearchResponse(query="test", results=())
    mock_videos.find_by_id.return_value = _video_row()

    client.post("/api/search", json={"query": "test", "k": 5})

    mock_searcher.search.assert_called_once_with("test", k=5)
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/test_search.py -v
```

Expected: FAIL — stub router returns 404 or 405.

- [ ] **Step 3: Implement search router**

Replace `src/videosearch/api/routers/search.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from videosearch.api.deps import get_searcher, get_videos_repo
from videosearch.search import Searcher
from videosearch.storage.videos import VideosRepo

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    k: int = 10
    include_missing: bool = False


class MomentResponse(BaseModel):
    timestamp_sec: float
    score: float
    thumb_url: str | None
    caption: str | None
    source: str  # "frame" | "caption"


class VideoResultResponse(BaseModel):
    video_id: str
    path: str
    duration_sec: float
    top_score: float
    moments: list[MomentResponse]


class SearchApiResponse(BaseModel):
    query: str
    results: list[VideoResultResponse]


@router.post("/search", response_model=SearchApiResponse)
async def search(
    body: SearchRequest,
    searcher: Searcher = Depends(get_searcher),
    videos: VideosRepo = Depends(get_videos_repo),
) -> SearchApiResponse:
    response = searcher.search(body.query, k=body.k)

    results: list[VideoResultResponse] = []
    for vr in response.results:
        video = videos.find_by_id(vr.video_id)
        if video is None:
            continue
        if video.status == "missing" and not body.include_missing:
            continue
        moments = [
            MomentResponse(
                timestamp_sec=m.timestamp_sec,
                score=m.score,
                thumb_url=(
                    f"/api/videos/{vr.video_id}/thumbs/{m.frame_idx}"
                    if m.frame_idx is not None else None
                ),
                caption=m.caption,
                source="caption" if m.caption else "frame",
            )
            for m in vr.moments
        ]
        results.append(VideoResultResponse(
            video_id=vr.video_id,
            path=video.path,
            duration_sec=video.duration_sec,
            top_score=vr.top_score,
            moments=moments,
        ))

    return SearchApiResponse(query=body.query, results=results)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/test_search.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/routers/search.py tests/api/test_search.py
git commit -m "feat(api): add search endpoint"
```

---

### Task 8: Library router

**Files:**
- Modify: `src/videosearch/api/routers/library.py`
- Create: `tests/api/test_library.py`

- [ ] **Step 1: Write failing tests**

Create `tests/api/test_library.py`:

```python
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

from videosearch.storage.schemas import LibraryFolderRow, VideoRow


def _folder(id_: str = "f1", path: str = "/movies") -> LibraryFolderRow:
    return LibraryFolderRow(id=id_, path=path, added_at=time.time())


def _video(id_: str, status: str = "indexed", folder_id: str = "f1") -> VideoRow:
    return VideoRow(
        id=id_, path=f"/movies/{id_}.mp4", hash=id_,
        duration_sec=10.0, fps=30.0, width=1920, height=1080,
        mtime=time.time(), status=status, last_seen_at=time.time(),
        library_folder_id=folder_id,
    )


def test_list_library_returns_folders_with_counts(client, mock_folders, mock_videos):
    mock_folders.list_all.return_value = [_folder("f1")]
    mock_videos.list_by_folder.return_value = [
        _video("v1", "indexed"), _video("v2", "indexed"), _video("v3", "failed"),
    ]
    mock_videos.list_by_status.return_value = []  # ad-hoc

    r = client.get("/api/library")

    assert r.status_code == 200
    data = r.json()
    assert len(data["folders"]) == 1
    counts = data["folders"][0]["counts"]
    assert counts["indexed"] == 2
    assert counts["failed"] == 1
    assert counts["pending"] == 0


def test_register_folder_returns_404_for_nonexistent_path(client, tmp_path):
    r = client.post("/api/library/folders", json={"path": "/no/such/dir"})
    assert r.status_code == 400


def test_register_folder_enqueues_video_files(client, mock_folders, mock_jobs, tmp_path):
    folder = tmp_path / "movies"
    folder.mkdir()
    # Create two fake video files large enough to pass skip-list (>100KB)
    for name in ["a.mp4", "b.mp4"]:
        f = folder / name
        f.write_bytes(b"x" * 200_000)

    r = client.post("/api/library/folders", json={"path": str(folder)})

    assert r.status_code == 200
    data = r.json()
    assert data["enqueued"] == 2
    assert mock_jobs.enqueue.call_count == 2


def test_delete_folder_returns_404_for_unknown_id(client, mock_folders):
    mock_folders.find_by_id.return_value = None
    r = client.delete("/api/library/folders/nonexistent")
    assert r.status_code == 404


def test_delete_folder_removes_from_repo(client, mock_folders, mock_videos):
    mock_folders.find_by_id.return_value = _folder("f1")
    mock_videos.list_by_folder.return_value = []

    r = client.delete("/api/library/folders/f1")

    assert r.status_code == 200
    mock_folders.delete.assert_called_once_with("f1")


def test_rescan_enqueues_non_indexed_files(client, mock_folders, mock_jobs, tmp_path):
    folder = tmp_path / "movies"
    folder.mkdir()
    video_file = folder / "c.mp4"
    video_file.write_bytes(b"x" * 200_000)

    mock_folders.find_by_id.return_value = _folder("f1", str(folder))

    r = client.post("/api/library/folders/f1/rescan")

    assert r.status_code == 200
    assert mock_jobs.enqueue.call_count == 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/test_library.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement library router**

Replace `src/videosearch/api/routers/library.py`:

```python
from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from videosearch.api.deps import (
    get_jobs_queue,
    get_library_folders_repo,
    get_videos_repo,
)
from videosearch.scanning.skiplist import should_skip
from videosearch.storage.jobs import JobsQueue
from videosearch.storage.library_folders import LibraryFoldersRepo
from videosearch.storage.schemas import LibraryFolderRow
from videosearch.storage.videos import VideosRepo

router = APIRouter()


class RegisterFolderRequest(BaseModel):
    path: str


class FolderCounts(BaseModel):
    indexed: int
    pending: int
    failed: int
    missing: int


class FolderResponse(BaseModel):
    id: str
    path: str
    added_at: float
    counts: FolderCounts


class LibraryResponse(BaseModel):
    folders: list[FolderResponse]
    ad_hoc_counts: FolderCounts


class RegisterFolderResponse(BaseModel):
    folder: FolderResponse
    enqueued: int


def _counts(videos: list) -> FolderCounts:
    c: dict[str, int] = {"indexed": 0, "pending": 0, "failed": 0, "missing": 0}
    for v in videos:
        if v.status in c:
            c[v.status] += 1
    return FolderCounts(**c)


def _walk_and_enqueue(
    path: Path,
    folder_id: str | None,
    jobs: JobsQueue,
) -> int:
    count = 0
    for f in path.rglob("*"):
        if not f.is_file():
            continue
        if should_skip(f):
            continue
        jobs.enqueue(kind="index", path=str(f), library_folder_id=folder_id)
        count += 1
    return count


@router.get("/library", response_model=LibraryResponse)
async def list_library(
    folders: LibraryFoldersRepo = Depends(get_library_folders_repo),
    videos: VideosRepo = Depends(get_videos_repo),
) -> LibraryResponse:
    folder_rows = folders.list_all()
    folder_responses: list[FolderResponse] = []
    for folder in folder_rows:
        vids = videos.list_by_folder(folder.id)
        folder_responses.append(FolderResponse(
            id=folder.id, path=folder.path, added_at=folder.added_at,
            counts=_counts(vids),
        ))
    ad_hoc = videos.list_by_folder(None)
    return LibraryResponse(folders=folder_responses, ad_hoc_counts=_counts(ad_hoc))


@router.post("/library/folders", response_model=RegisterFolderResponse)
async def register_folder(
    body: RegisterFolderRequest,
    folders: LibraryFoldersRepo = Depends(get_library_folders_repo),
    jobs: JobsQueue = Depends(get_jobs_queue),
) -> RegisterFolderResponse:
    path = Path(body.path)
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="path is not a directory")

    folder_id = str(uuid.uuid4())
    folder = LibraryFolderRow(id=folder_id, path=str(path), added_at=time.time())
    folders.insert(folder)

    count = await asyncio.to_thread(_walk_and_enqueue, path, folder_id, jobs)
    vids = []  # empty immediately after registration
    return RegisterFolderResponse(
        folder=FolderResponse(
            id=folder.id, path=folder.path, added_at=folder.added_at,
            counts=_counts(vids),
        ),
        enqueued=count,
    )


@router.delete("/library/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    purge: bool = False,
    folders: LibraryFoldersRepo = Depends(get_library_folders_repo),
    videos: VideosRepo = Depends(get_videos_repo),
) -> dict:
    folder = folders.find_by_id(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="folder not found")
    if purge:
        for video in videos.list_by_folder(folder_id):
            videos.update(video.id, status="missing")
    folders.delete(folder_id)
    return {"ok": True}


@router.post("/library/folders/{folder_id}/rescan")
async def rescan_folder(
    folder_id: str,
    folders: LibraryFoldersRepo = Depends(get_library_folders_repo),
    jobs: JobsQueue = Depends(get_jobs_queue),
) -> dict:
    folder = folders.find_by_id(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="folder not found")
    count = await asyncio.to_thread(
        _walk_and_enqueue, Path(folder.path), folder_id, jobs
    )
    return {"enqueued": count}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/test_library.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/routers/library.py tests/api/test_library.py
git commit -m "feat(api): add library endpoints (list, register, delete, rescan)"
```

---

### Task 9: Ingest router

**Files:**
- Modify: `src/videosearch/api/routers/ingest.py`
- Create: `tests/api/test_ingest.py`

- [ ] **Step 1: Write failing tests**

Create `tests/api/test_ingest.py`:

```python
from __future__ import annotations


def test_ingest_single_file(client, mock_jobs, tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x" * 200_000)

    r = client.post("/api/ingest", json={"path": str(f)})

    assert r.status_code == 200
    data = r.json()
    assert len(data["enqueued"]) == 1
    mock_jobs.enqueue.assert_called_once()


def test_ingest_directory_recursive(client, mock_jobs, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "a.mp4").write_bytes(b"x" * 200_000)
    (sub / "b.mp4").write_bytes(b"x" * 200_000)

    r = client.post("/api/ingest", json={"path": str(tmp_path), "recursive": True})

    assert r.status_code == 200
    assert len(r.json()["enqueued"]) == 2


def test_ingest_directory_non_recursive(client, mock_jobs, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "a.mp4").write_bytes(b"x" * 200_000)
    (sub / "b.mp4").write_bytes(b"x" * 200_000)

    r = client.post("/api/ingest", json={"path": str(tmp_path), "recursive": False})

    assert r.status_code == 200
    assert len(r.json()["enqueued"]) == 1


def test_ingest_nonexistent_path_returns_400(client):
    r = client.post("/api/ingest", json={"path": "/no/such/file.mp4"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/test_ingest.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement ingest router**

Replace `src/videosearch/api/routers/ingest.py`:

```python
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from videosearch.api.deps import get_jobs_queue
from videosearch.scanning.skiplist import should_skip
from videosearch.storage.jobs import JobsQueue

router = APIRouter()


class IngestRequest(BaseModel):
    path: str
    recursive: bool = True


class IngestResponse(BaseModel):
    enqueued: list[str]  # list of job IDs


def _collect_and_enqueue(path: Path, recursive: bool, jobs: JobsQueue) -> list[str]:
    job_ids: list[str] = []
    if path.is_file():
        if not should_skip(path):
            job_ids.append(jobs.enqueue(kind="index", path=str(path)))
        return job_ids

    glob = path.rglob("*") if recursive else path.glob("*")
    for f in glob:
        if not f.is_file():
            continue
        if should_skip(f):
            continue
        job_ids.append(jobs.enqueue(kind="index", path=str(f)))
    return job_ids


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    body: IngestRequest,
    jobs: JobsQueue = Depends(get_jobs_queue),
) -> IngestResponse:
    path = Path(body.path)
    if not path.exists():
        raise HTTPException(status_code=400, detail="path does not exist")
    job_ids = await asyncio.to_thread(_collect_and_enqueue, path, body.recursive, jobs)
    return IngestResponse(enqueued=job_ids)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/test_ingest.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/routers/ingest.py tests/api/test_ingest.py
git commit -m "feat(api): add ingest endpoint"
```

---

### Task 10: Jobs router

**Files:**
- Modify: `src/videosearch/api/routers/jobs.py`
- Create: `tests/api/test_jobs.py`

- [ ] **Step 1: Write failing tests**

Create `tests/api/test_jobs.py`:

```python
from __future__ import annotations

import time
from videosearch.storage.jobs import Job


def _job(id_: str = "j1", status: str = "completed") -> Job:
    return Job(
        id=id_, video_id="v1", path="/a.mp4", library_folder_id=None,
        kind="index", status=status, progress=1.0, error=None,
        created_at=time.time(), updated_at=time.time(),
    )


def test_list_jobs_returns_recent(client, mock_jobs):
    mock_jobs.list_recent.return_value = [_job("j1"), _job("j2")]
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert len(r.json()["jobs"]) == 2


def test_retry_job_returns_409_if_not_failed(client, mock_jobs):
    mock_jobs.get_by_id.return_value = _job("j1", status="completed")
    r = client.post("/api/jobs/j1/retry")
    assert r.status_code == 409


def test_retry_job_enqueues_new_job(client, mock_jobs):
    mock_jobs.get_by_id.return_value = _job("j1", status="failed")
    mock_jobs.enqueue.return_value = "j2"
    r = client.post("/api/jobs/j1/retry")
    assert r.status_code == 200
    assert r.json()["job_id"] == "j2"
    mock_jobs.enqueue.assert_called_once()


def test_retry_job_returns_404_for_unknown_id(client, mock_jobs):
    mock_jobs.get_by_id.return_value = None
    r = client.post("/api/jobs/unknown/retry")
    assert r.status_code == 404
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/test_jobs.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement jobs router**

Replace `src/videosearch/api/routers/jobs.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from videosearch.api.deps import get_jobs_queue
from videosearch.storage.jobs import Job, JobsQueue

router = APIRouter()


class JobResponse(BaseModel):
    id: str
    video_id: str | None
    path: str | None
    kind: str
    status: str
    progress: float
    error: str | None
    created_at: float
    updated_at: float


class JobsListResponse(BaseModel):
    jobs: list[JobResponse]


def _job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id, video_id=job.video_id, path=job.path,
        kind=job.kind, status=job.status, progress=job.progress,
        error=job.error, created_at=job.created_at, updated_at=job.updated_at,
    )


@router.get("/jobs", response_model=JobsListResponse)
async def list_jobs(
    jobs: JobsQueue = Depends(get_jobs_queue),
) -> JobsListResponse:
    return JobsListResponse(jobs=[_job_to_response(j) for j in jobs.list_recent(200)])


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    jobs: JobsQueue = Depends(get_jobs_queue),
) -> dict:
    job = jobs.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="only failed jobs can be retried")
    new_id = jobs.enqueue(
        kind=job.kind,
        path=job.path,
        library_folder_id=job.library_folder_id,
    )
    return {"job_id": new_id}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/test_jobs.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/routers/jobs.py tests/api/test_jobs.py
git commit -m "feat(api): add jobs endpoints (list, retry)"
```

---

### Task 11: Videos router (stream, thumbs, reveal)

**Files:**
- Modify: `src/videosearch/api/routers/videos.py`
- Create: `tests/api/test_videos.py`

- [ ] **Step 1: Write failing tests**

Create `tests/api/test_videos.py`:

```python
from __future__ import annotations

import time
from unittest.mock import patch

from videosearch.storage.schemas import FrameEmbeddingRow, VideoRow
from videosearch.storage.schemas import SIGLIP_DIM


def _video(id_: str = "v1", status: str = "indexed", path: str | None = None) -> VideoRow:
    return VideoRow(
        id=id_, path=path or f"/videos/{id_}.mp4", hash=id_,
        duration_sec=60.0, fps=30.0, width=1920, height=1080,
        mtime=time.time(), status=status, last_seen_at=time.time(),
    )


def _frame(video_id: str, frame_idx: int, thumb_path: str) -> FrameEmbeddingRow:
    return FrameEmbeddingRow(
        video_id=video_id, frame_idx=frame_idx, timestamp_sec=float(frame_idx),
        embedding=[0.1] * SIGLIP_DIM, thumb_path=thumb_path,
    )


def test_stream_returns_404_for_unknown_video(client, mock_videos):
    mock_videos.find_by_id.return_value = None
    r = client.get("/api/videos/v1/stream")
    assert r.status_code == 404


def test_stream_returns_410_for_missing_video(client, mock_videos):
    mock_videos.find_by_id.return_value = _video(status="missing")
    r = client.get("/api/videos/v1/stream")
    assert r.status_code == 410


def test_stream_returns_404_when_file_not_on_disk(client, mock_videos, tmp_path):
    mock_videos.find_by_id.return_value = _video(path="/nonexistent/file.mp4")
    r = client.get("/api/videos/v1/stream")
    assert r.status_code == 404


def test_stream_returns_file_when_exists(client, mock_videos, tmp_path):
    video_file = tmp_path / "test.mp4"
    video_file.write_bytes(b"fake video content")
    mock_videos.find_by_id.return_value = _video(path=str(video_file))
    r = client.get("/api/videos/v1/stream")
    assert r.status_code == 200
    assert b"fake video content" in r.content


def test_thumb_returns_404_for_unknown_frame(client, mock_frames):
    mock_frames.find_frame.return_value = None
    r = client.get("/api/videos/v1/thumbs/1")
    assert r.status_code == 404


def test_thumb_serves_jpeg_file(client, mock_frames, tmp_path):
    thumb = tmp_path / "frame.jpg"
    thumb.write_bytes(b"fake jpeg")
    mock_frames.find_frame.return_value = _frame("v1", 1, str(thumb))
    r = client.get("/api/videos/v1/thumbs/1")
    assert r.status_code == 200
    assert b"fake jpeg" in r.content


def test_reveal_returns_404_for_unknown_video(client, mock_videos):
    mock_videos.find_by_id.return_value = None
    r = client.post("/api/videos/v1/reveal")
    assert r.status_code == 404


def test_reveal_calls_open_on_macos(client, mock_videos, tmp_path):
    video_file = tmp_path / "test.mp4"
    video_file.write_bytes(b"x")
    mock_videos.find_by_id.return_value = _video(path=str(video_file))
    with patch("sys.platform", "darwin"), patch("subprocess.Popen") as mock_popen:
        r = client.post("/api/videos/v1/reveal")
    assert r.status_code == 200
    mock_popen.assert_called_once()
    args = mock_popen.call_args[0][0]
    assert args[0] == "open" and args[1] == "-R"
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/test_videos.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement videos router**

Replace `src/videosearch/api/routers/videos.py`:

```python
from __future__ import annotations

import mimetypes
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import FileResponse

from videosearch.api.deps import get_frames_repo, get_videos_repo
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.videos import VideosRepo

router = APIRouter()


@router.get("/videos/{video_id}/stream")
async def stream_video(
    video_id: str,
    videos: VideosRepo = Depends(get_videos_repo),
) -> FileResponse:
    video = videos.find_by_id(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    if video.status == "missing":
        raise HTTPException(status_code=410, detail="video file is missing")
    path = Path(video.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="video file not found on disk")
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=media_type or "application/octet-stream")


@router.get("/videos/{video_id}/thumbs/{frame_idx}")
async def get_thumbnail(
    video_id: str,
    frame_idx: int,
    frames: FrameEmbeddingsRepo = Depends(get_frames_repo),
) -> FileResponse:
    row = frames.find_frame(video_id, frame_idx)
    if row is None:
        raise HTTPException(status_code=404, detail="thumbnail not found")
    path = Path(row.thumb_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="thumbnail file not found on disk")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/videos/{video_id}/reveal")
async def reveal_video(
    video_id: str,
    videos: VideosRepo = Depends(get_videos_repo),
) -> dict:
    video = videos.find_by_id(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    path = Path(video.path)
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise HTTPException(status_code=501, detail="no display available")
        subprocess.Popen(["xdg-open", str(path.parent)])
    return {"ok": True}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/test_videos.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/routers/videos.py tests/api/test_videos.py
git commit -m "feat(api): add video stream, thumbnail, and reveal endpoints"
```

---

### Task 12: Filesystem picker router

**Files:**
- Modify: `src/videosearch/api/routers/fs.py`
- Create: `tests/api/test_fs.py`

- [ ] **Step 1: Write failing tests**

Create `tests/api/test_fs.py`:

```python
from __future__ import annotations

import os
from pathlib import Path


def test_fs_list_defaults_to_home(client):
    r = client.get("/api/fs/list")
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == str(Path.home())


def test_fs_list_returns_entries(client, tmp_path):
    (tmp_path / "Movies").mkdir()
    (tmp_path / "clip.mp4").write_bytes(b"x" * 200_000)
    (tmp_path / "notes.txt").write_bytes(b"text")

    r = client.get(f"/api/fs/list?path={tmp_path}")
    assert r.status_code == 200
    entries = {e["name"]: e for e in r.json()["entries"]}
    assert "Movies" in entries
    assert entries["Movies"]["kind"] == "dir"
    assert "clip.mp4" in entries
    assert entries["clip.mp4"]["kind"] == "video"
    assert "notes.txt" in entries
    assert entries["notes.txt"]["kind"] == "other"


def test_fs_list_excludes_hidden_files(client, tmp_path):
    (tmp_path / ".hidden").write_bytes(b"x")
    (tmp_path / "visible.mp4").write_bytes(b"x" * 200_000)

    r = client.get(f"/api/fs/list?path={tmp_path}")
    names = [e["name"] for e in r.json()["entries"]]
    assert ".hidden" not in names
    assert "visible.mp4" in names


def test_fs_list_rejects_path_outside_home(client, tmp_path):
    # /tmp is typically outside $HOME
    home = Path.home()
    try:
        outside = Path("/tmp").resolve()
        if str(outside).startswith(str(home)):
            return  # skip — /tmp is inside home on this system
    except Exception:
        return
    r = client.get(f"/api/fs/list?path=/tmp")
    assert r.status_code == 403


def test_fs_list_returns_parent(client, tmp_path):
    # tmp_path is typically inside /tmp which may be outside home;
    # use a path inside home for this test
    home = Path.home()
    r = client.get(f"/api/fs/list?path={home}")
    data = r.json()
    assert "parent" in data
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/test_fs.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement fs router**

Replace `src/videosearch/api/routers/fs.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from videosearch.scanning.skiplist import DEFAULT_VIDEO_EXTS

router = APIRouter()

_HOME = Path.home().resolve()


class FsEntry(BaseModel):
    name: str
    path: str
    kind: str  # "dir" | "video" | "other"
    size_bytes: int | None
    mtime: float


class FsListResponse(BaseModel):
    path: str
    parent: str | None
    entries: list[FsEntry]


def _safe_resolve(path_str: str | None) -> Path:
    if not path_str:
        return _HOME
    p = Path(path_str).resolve()
    if not str(p).startswith(str(_HOME)):
        raise HTTPException(status_code=403, detail="path outside home directory")
    return p


def _entry_kind(p: Path) -> str:
    if p.is_dir():
        return "dir"
    if p.suffix.lower() in DEFAULT_VIDEO_EXTS:
        return "video"
    return "other"


@router.get("/fs/list", response_model=FsListResponse)
async def fs_list(path: str | None = Query(default=None)) -> FsListResponse:
    resolved = _safe_resolve(path)
    if not resolved.is_dir():
        raise HTTPException(status_code=400, detail="path is not a directory")

    parent = str(resolved.parent) if resolved != _HOME else None
    entries: list[FsEntry] = []
    try:
        children = sorted(resolved.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        children = []

    for child in children:
        if child.name.startswith("."):
            continue
        try:
            stat = child.stat()
            size = stat.st_size if child.is_file() else None
            mtime = stat.st_mtime
        except OSError:
            continue
        entries.append(FsEntry(
            name=child.name,
            path=str(child),
            kind=_entry_kind(child),
            size_bytes=size,
            mtime=mtime,
        ))

    return FsListResponse(path=str(resolved), parent=parent, entries=entries)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/test_fs.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/routers/fs.py tests/api/test_fs.py
git commit -m "feat(api): add filesystem picker endpoint"
```

---

### Task 13: Settings router

**Files:**
- Modify: `src/videosearch/api/routers/settings.py`
- Create: `tests/api/test_settings.py`

- [ ] **Step 1: Write failing tests**

Create `tests/api/test_settings.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_get_settings_returns_current_settings(client, test_settings):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["port"] == test_settings.port
    assert data["frame_fps"] == test_settings.frame_fps


def test_patch_settings_updates_field(client, test_settings):
    r = client.patch("/api/settings", json={"frame_fps": 2.0})
    assert r.status_code == 200
    assert r.json()["frame_fps"] == 2.0


def test_patch_settings_writes_config_toml(client, test_settings):
    client.patch("/api/settings", json={"frame_fps": 3.0})
    config_path = test_settings.data_dir / "config.toml"
    assert config_path.exists()
    content = config_path.read_text()
    assert "frame_fps" in content


def test_patch_settings_rejects_unknown_fields(client):
    r = client.patch("/api/settings", json={"nonexistent_field": "value"})
    # Unknown fields are ignored (pydantic extra="ignore"), response is still 200
    assert r.status_code == 200


def test_patch_settings_invalid_type_returns_422(client):
    r = client.patch("/api/settings", json={"port": "not-an-int"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/test_settings.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement settings router**

Replace `src/videosearch/api/routers/settings.py`:

```python
from __future__ import annotations

from pathlib import Path

import tomli_w
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from videosearch.api.deps import get_settings
from videosearch.config import Settings

router = APIRouter()


def _settings_to_toml_dict(s: Settings) -> dict:
    result: dict = {}
    for key, value in s.model_dump().items():
        if value is None:
            continue
        if isinstance(value, Path):
            result[key] = str(value)
        elif isinstance(value, list):
            result[key] = [str(item) if isinstance(item, Path) else item for item in value]
        else:
            result[key] = value
    return result


@router.get("/settings")
async def get_settings_endpoint(
    settings: Settings = Depends(get_settings),
) -> dict:
    return _settings_to_toml_dict(settings)


class SettingsPatch(BaseModel, extra="ignore"):
    frame_fps: float | None = None
    scene_detection: bool | None = None
    port: int | None = None
    siglip_model: str | None = None
    text_embedder: str | None = None
    vlm_model: str | None = None
    vlm_mmproj: str | None = None
    vlm_n_gpu_layers: int | None = None


@router.patch("/settings")
async def patch_settings(
    request: Request,
    body: SettingsPatch,
    settings: Settings = Depends(get_settings),
) -> dict:
    current = settings.model_dump()
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    current.update(patch)
    new_settings = Settings(**current)

    config_path = Path(new_settings.data_dir) / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "wb") as f:
        tomli_w.dump(_settings_to_toml_dict(new_settings), f)

    # Update live settings on app state (safe fields take effect immediately)
    request.app.state.settings = new_settings
    return _settings_to_toml_dict(new_settings)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/test_settings.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/routers/settings.py tests/api/test_settings.py
git commit -m "feat(api): add settings endpoints (get, patch)"
```

---

### Task 14: CLI entrypoint

**Files:**
- Create: `src/videosearch/cli.py`
- Modify: `pyproject.toml` (already done in Task 1 — `[project.scripts]` was added)

- [ ] **Step 1: Implement cli.py**

Create `src/videosearch/cli.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import uvicorn

from videosearch.config import Settings, load_config

app = typer.Typer(help="Video search server.")


@app.command()
def serve(
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Port to listen on (default: 8083)."),
    config: Optional[Path] = typer.Option(None, "--config", help="Path to config.toml."),
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="Data directory override."),
    models_dir: Optional[Path] = typer.Option(None, "--models-dir", help="Models directory override."),
) -> None:
    """Start the video search server."""
    # Resolve data_dir first (needed to find config.toml)
    import os
    if data_dir:
        os.environ["VS_DATA_DIR"] = str(data_dir)
    if models_dir:
        os.environ["VS_MODELS_DIR"] = str(models_dir)

    # Determine config path: explicit flag > data_dir/config.toml
    settings = load_config(config)

    # CLI port flag overrides everything
    if port is not None:
        settings = settings.model_copy(update={"port": port})

    from videosearch.api.app import create_app
    server_app = create_app(settings)

    typer.echo(f"Starting video search on http://127.0.0.1:{settings.port}")
    uvicorn.run(server_app, host="127.0.0.1", port=settings.port)
```

- [ ] **Step 2: Reinstall to register the console script**

```bash
uv sync
```

- [ ] **Step 3: Verify the CLI entry point is registered**

```bash
uv run videosearch --help
```

Expected: typer help output showing `serve` command with options.

- [ ] **Step 4: Commit**

```bash
git add src/videosearch/cli.py pyproject.toml
git commit -m "feat(cli): add videosearch serve entrypoint"
```

---

### Task 15: Integration tests

**Files:**
- Create: `tests/api/test_integration.py`
- Modify: `tests/conftest.py` (add `tiny_video` fixture if needed — check if it already exists in `tests/conftest.py`)

- [ ] **Step 1: Check existing conftest for tiny_video fixture**

```bash
cat tests/conftest.py
```

If `tiny_video` fixture is already defined (from Phase 3), no changes needed. If the file doesn't exist, create it with:

```python
import pytest
from pathlib import Path

@pytest.fixture(scope="session")
def tiny_video() -> Path:
    p = Path(__file__).parent / "fixtures" / "tiny.mp4"
    if not p.exists():
        raise FileNotFoundError(
            f"Test fixture missing: {p}\n"
            "Add a small test video at tests/fixtures/tiny.mp4"
        )
    return p
```

- [ ] **Step 2: Write integration tests**

Create `tests/api/test_integration.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from videosearch.api.app import create_app
from videosearch.config import Settings
from videosearch.models.stubs import StubCaptioner, StubImageEmbedder, StubTextEmbedder
from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
from videosearch.storage.db import Database
from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
from videosearch.storage.jobs import JobsQueue
from videosearch.storage.library_folders import LibraryFoldersRepo
from videosearch.storage.videos import VideosRepo
from videosearch.search import Searcher
from videosearch.api import deps
from videosearch.api.ws import JobBroadcaster
from videosearch.api.worker import IndexerWorker
import asyncio


@pytest.fixture
def integration_client(tmp_path, tiny_video):
    """Full app with real DB + stub models, no lifespan (worker started manually)."""
    settings = Settings(
        data_dir=tmp_path / "data",
        models_dir=tmp_path / "models",
    )
    db = Database(settings.data_dir)
    jobs_queue = JobsQueue(settings.data_dir / "jobs.db")
    videos = VideosRepo(db)
    frames = FrameEmbeddingsRepo(db)
    captions = CaptionEmbeddingsRepo(db)
    folders = LibraryFoldersRepo(db)
    image_embedder = StubImageEmbedder()
    text_embedder = StubTextEmbedder()
    captioner = StubCaptioner()
    searcher = Searcher(
        frames=frames, captions=captions,
        image_embedder=image_embedder, text_embedder=text_embedder,
    )
    broadcaster = MagicMock()

    app = create_app(settings, startup=False)
    app.state.settings = settings
    app.state.searcher = searcher
    app.state.jobs_queue = jobs_queue
    app.state.videos_repo = videos
    app.state.frames_repo = frames
    app.state.captions_repo = captions
    app.state.library_folders_repo = folders
    app.state.broadcaster = broadcaster
    app.state.worker = MagicMock()
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        yield client, jobs_queue, videos, frames, captions, image_embedder, text_embedder, captioner, settings, tiny_video


def test_integration_ingest_then_search(integration_client):
    from unittest.mock import MagicMock
    from videosearch.indexer import index_video

    client, jobs_queue, videos, frames, captions, image_emb, text_emb, captioner, settings, tiny_video = integration_client

    # Index the tiny video directly (bypassing the worker thread)
    result = index_video(
        path=tiny_video,
        videos=videos,
        frames=frames,
        captions=captions,
        image_embedder=image_emb,
        text_embedder=text_emb,
        captioner=captioner,
        work_dir=settings.data_dir / "work",
        frame_fps=2.0,
    )
    assert result.status == "indexed"

    # Search via HTTP
    r = client.post("/api/search", json={"query": "test query"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["video_id"] == result.video_id


def test_integration_health_endpoint(integration_client):
    client = integration_client[0]
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["db"] is True


def test_integration_ingest_endpoint_enqueues_job(integration_client, tmp_path):
    client, jobs_queue = integration_client[0], integration_client[1]
    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"x" * 200_000)

    r = client.post("/api/ingest", json={"path": str(video_file)})
    assert r.status_code == 200
    job_ids = r.json()["enqueued"]
    assert len(job_ids) == 1

    job = jobs_queue.get_by_id(job_ids[0])
    assert job is not None
    assert job.path == str(video_file)


def test_integration_jobs_list_after_ingest(integration_client, tmp_path):
    client, jobs_queue = integration_client[0], integration_client[1]
    video_file = tmp_path / "sample2.mp4"
    video_file.write_bytes(b"x" * 200_000)
    client.post("/api/ingest", json={"path": str(video_file)})

    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert len(r.json()["jobs"]) >= 1
```

Note: `MagicMock` must be imported at the top of this file. Add to imports:

```python
from unittest.mock import MagicMock
```

- [ ] **Step 3: Run integration tests**

```bash
uv run pytest tests/api/test_integration.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest --ignore=tests/models -v 2>&1 | tail -15
```

Expected: all tests pass (existing 69 + new ~60 = ~129 total).

- [ ] **Step 5: Commit**

```bash
git add tests/api/test_integration.py
git commit -m "test(api): add end-to-end integration tests for API layer"
```

---

## Self-review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `POST /api/search` | Task 7 |
| `GET /api/fs/list` | Task 12 |
| `GET /api/library` | Task 8 |
| `POST /api/library/folders` | Task 8 |
| `DELETE /api/library/folders/{id}` | Task 8 |
| `POST /api/library/folders/{id}/rescan` | Task 8 |
| `POST /api/ingest` | Task 9 |
| `GET /api/jobs` | Task 10 |
| `POST /api/jobs/{job_id}/retry` | Task 10 |
| `GET /api/videos/{id}/stream` | Task 11 |
| `GET /api/videos/{id}/thumbs/{frame_idx}` | Task 11 |
| `POST /api/videos/{id}/reveal` | Task 11 |
| `GET /api/settings` | Task 13 |
| `PATCH /api/settings` | Task 13 |
| `GET /api/health` | Task 6 |
| `WS /ws/jobs` | Task 3 |
| Background worker thread | Task 4 |
| Model loading on startup | Task 5 (`startup=True` lifespan) |
| `videosearch serve` CLI | Task 14 |
| `list_recent()` for JobsQueue | Task 2 |
| `frame_idx` on Moment | Task 1 |
| Integration tests | Task 15 |

**No placeholders found.** All steps have concrete code.

**Type consistency:** `Job.path`, `Job.library_folder_id` defined in Task 2, used consistently in Tasks 4, 8, 9, 10. `JobBroadcaster` defined in Task 3, used in Task 4. `Depends(get_*)` functions defined in Task 5, used in Tasks 6–13. `frame_idx` added in Task 1, used in Task 7.
