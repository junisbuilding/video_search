# Filesystem Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `watchdog`-based filesystem watcher so new, modified, and deleted video files in registered library folders are detected automatically.

**Architecture:** A single `watchdog.observers.Observer` runs in one background thread. `LibraryWatcher` wraps it with `add_watch`/`remove_watch`/`status` methods. `FolderEventHandler` (one per folder) calls `JobsQueue` and `VideosRepo` directly on the watchdog thread — both are thread-safe. The watcher is seeded from DB-persisted folders on lifespan startup.

**Tech Stack:** `watchdog>=4.0`, existing `JobsQueue` (SQLite), `VideosRepo` (LanceDB), FastAPI lifespan/DI pattern already in use.

---

### Context: key existing files

- `src/videosearch/scanning/skiplist.py` — `should_skip(path: Path) -> bool`. Checks dotfiles, extension, size (requires file to exist). `DEFAULT_VIDEO_EXTS` is the set of valid extensions.
- `src/videosearch/storage/videos.py` — `VideosRepo`. `find_by_hash`, `find_by_id`, `update(id_, **fields)`, `list_by_status`, `list_by_folder`. No `find_by_path` yet.
- `src/videosearch/storage/jobs.py` — `JobsQueue.enqueue(kind, path, library_folder_id)`.
- `src/videosearch/api/app.py` — lifespan creates all state objects and stores on `app.state`. `startup=False` skips all of this (used in tests).
- `src/videosearch/api/deps.py` — dep functions of the form `def get_X(conn: HTTPConnection) -> X: return conn.app.state.x`.
- `tests/api/conftest.py` — `client` fixture builds a `TestClient` with `startup=False` and overrides all deps via `app.dependency_overrides`.

---

### Task 1: Add watchdog dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add watchdog to pyproject.toml**

In `pyproject.toml`, add `"watchdog>=4.0",` to the `dependencies` list after `"tomli-w>=1.0",`:

```toml
    "tomli-w>=1.0",
    "watchdog>=4.0",
```

- [ ] **Step 2: Install and verify**

```bash
uv sync
python -c "import watchdog; print(watchdog.__version__)"
```

Expected: prints a version number like `6.0.0`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add watchdog dependency"
```

---

### Task 2: Add `VideosRepo.find_by_path()`

**Files:**
- Modify: `src/videosearch/storage/videos.py` (after `find_by_id`, ~line 28)
- Test: `tests/storage/test_videos.py`

The `on_deleted` event handler needs to look up a video by its filesystem path to mark it missing. `VideosRepo` currently has no such method.

- [ ] **Step 1: Write the failing tests**

Append to `tests/storage/test_videos.py`:

```python
def test_find_by_path_returns_video(tmp_path: Path):
    repo = VideosRepo(Database(tmp_path))
    v = _video(path="/videos/movie.mp4", hash="h_path1")
    repo.insert(v)
    found = repo.find_by_path("/videos/movie.mp4")
    assert found is not None
    assert found.id == v.id


def test_find_by_path_returns_none_when_missing(tmp_path: Path):
    repo = VideosRepo(Database(tmp_path))
    assert repo.find_by_path("/no/such/path.mp4") is None
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/storage/test_videos.py::test_find_by_path_returns_video -v
```

Expected: `FAILED` — `AttributeError: 'VideosRepo' object has no attribute 'find_by_path'`

- [ ] **Step 3: Implement `find_by_path`**

In `src/videosearch/storage/videos.py`, add after `find_by_id`:

```python
    def find_by_path(self, path: str) -> VideoRow | None:
        results = (
            self._table.search()
            .where(f"path = {_sql_literal(path)}")
            .limit(1)
            .to_list()
        )
        return VideoRow(**results[0]) if results else None
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/storage/test_videos.py -v
```

Expected: all pass including the two new tests.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/storage/videos.py tests/storage/test_videos.py
git commit -m "feat: add VideosRepo.find_by_path()"
```

---

### Task 3: Implement `watcher.py`

**Files:**
- Create: `src/videosearch/scanning/watcher.py`
- Create: `tests/scanning/test_watcher.py`

`FolderEventHandler` handles watchdog events on the watchdog thread. For `on_created`/`on_modified`, it calls `should_skip()` (file must exist). For `on_deleted`, it cannot call `should_skip()` (file is gone) — it checks the name only using `_is_video_by_name()`. `LibraryWatcher` owns one `Observer` and manages watches + status.

- [ ] **Step 1: Write failing tests**

Create `tests/scanning/test_watcher.py`:

```python
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from watchdog.events import (
    DirCreatedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
)

from videosearch.scanning.watcher import FolderEventHandler, LibraryWatcher, WatchStatus
from videosearch.storage.schemas import VideoRow


def _video_row(id_: str, path: str) -> VideoRow:
    now = time.time()
    return VideoRow(
        id=id_, path=path, hash=id_, duration_sec=10.0, fps=30.0,
        width=320, height=240, mtime=now, status="indexed", last_seen_at=now,
    )


class TestFolderEventHandler:
    def setup_method(self):
        self.jobs = MagicMock()
        self.videos = MagicMock()
        self.handler = FolderEventHandler("folder-1", self.jobs, self.videos)

    def test_on_created_enqueues_video(self, tmp_path):
        path = tmp_path / "movie.mp4"
        path.write_bytes(b"x" * 200_000)
        self.handler.on_created(FileCreatedEvent(str(path)))
        self.jobs.enqueue.assert_called_once_with(
            kind="index", path=str(path), library_folder_id="folder-1"
        )

    def test_on_created_skips_dotfile(self, tmp_path):
        path = tmp_path / ".hidden.mp4"
        path.write_bytes(b"x" * 200_000)
        self.handler.on_created(FileCreatedEvent(str(path)))
        self.jobs.enqueue.assert_not_called()

    def test_on_created_skips_non_video_extension(self, tmp_path):
        path = tmp_path / "notes.txt"
        path.write_bytes(b"x" * 200_000)
        self.handler.on_created(FileCreatedEvent(str(path)))
        self.jobs.enqueue.assert_not_called()

    def test_on_created_ignores_directory_event(self):
        self.handler.on_created(DirCreatedEvent("/some/dir"))
        self.jobs.enqueue.assert_not_called()

    def test_on_modified_enqueues_video(self, tmp_path):
        path = tmp_path / "movie.mp4"
        path.write_bytes(b"x" * 200_000)
        self.handler.on_modified(FileModifiedEvent(str(path)))
        self.jobs.enqueue.assert_called_once_with(
            kind="index", path=str(path), library_folder_id="folder-1"
        )

    def test_on_deleted_marks_known_video_missing(self):
        path = "/videos/movie.mp4"
        self.videos.find_by_path.return_value = _video_row("v1", path)
        self.handler.on_deleted(FileDeletedEvent(path))
        self.videos.find_by_path.assert_called_once_with(path)
        self.videos.update.assert_called_once_with("v1", status="missing")

    def test_on_deleted_does_nothing_for_unknown_path(self):
        self.videos.find_by_path.return_value = None
        self.handler.on_deleted(FileDeletedEvent("/videos/movie.mp4"))
        self.videos.update.assert_not_called()

    def test_on_deleted_skips_non_video_name(self):
        self.handler.on_deleted(FileDeletedEvent("/videos/notes.txt"))
        self.videos.find_by_path.assert_not_called()

    def test_on_moved_marks_src_missing_and_enqueues_dst(self, tmp_path):
        src = "/videos/old.mp4"
        dst = tmp_path / "new.mp4"
        dst.write_bytes(b"x" * 200_000)
        self.videos.find_by_path.return_value = _video_row("v1", src)
        self.handler.on_moved(FileMovedEvent(src, str(dst)))
        self.videos.update.assert_called_once_with("v1", status="missing")
        self.jobs.enqueue.assert_called_once_with(
            kind="index", path=str(dst), library_folder_id="folder-1"
        )


class TestLibraryWatcher:
    def test_status_empty_initially(self):
        watcher = LibraryWatcher(MagicMock(), MagicMock())
        watcher.start()
        try:
            assert watcher.status() == []
        finally:
            watcher.stop()

    def test_add_watch_records_active_status(self, tmp_path):
        watcher = LibraryWatcher(MagicMock(), MagicMock())
        watcher.start()
        try:
            watcher.add_watch("folder-1", tmp_path)
            statuses = watcher.status()
            assert len(statuses) == 1
            assert statuses[0].folder_id == "folder-1"
            assert statuses[0].path == str(tmp_path)
            assert statuses[0].active is True
            assert statuses[0].error is None
        finally:
            watcher.stop()

    def test_remove_watch_clears_status(self, tmp_path):
        watcher = LibraryWatcher(MagicMock(), MagicMock())
        watcher.start()
        try:
            watcher.add_watch("folder-1", tmp_path)
            watcher.remove_watch("folder-1")
            assert watcher.status() == []
        finally:
            watcher.stop()

    def test_add_watch_oserror_records_error(self, tmp_path):
        watcher = LibraryWatcher(MagicMock(), MagicMock())
        watcher.start()
        try:
            with patch.object(watcher._observer, "schedule", side_effect=OSError("inotify limit")):
                watcher.add_watch("folder-1", tmp_path)
            statuses = watcher.status()
            assert len(statuses) == 1
            assert statuses[0].active is False
            assert statuses[0].error is not None
            assert "inotify limit" in statuses[0].error
        finally:
            watcher.stop()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/scanning/test_watcher.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'videosearch.scanning.watcher'`

- [ ] **Step 3: Create `watcher.py`**

Create `src/videosearch/scanning/watcher.py`:

```python
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from videosearch.scanning.skiplist import DEFAULT_VIDEO_EXTS, should_skip
from videosearch.storage.jobs import JobsQueue
from videosearch.storage.videos import VideosRepo


@dataclass(frozen=True)
class WatchStatus:
    folder_id: str
    path: str
    active: bool
    error: str | None


def _is_video_by_name(path: Path) -> bool:
    """Check if path looks like a video file by name alone (no filesystem access)."""
    if path.name.startswith("."):
        return False
    return path.suffix.lower() in DEFAULT_VIDEO_EXTS


class FolderEventHandler(FileSystemEventHandler):
    def __init__(self, folder_id: str, jobs: JobsQueue, videos: VideosRepo) -> None:
        super().__init__()
        self._folder_id = folder_id
        self._jobs = jobs
        self._videos = videos

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if should_skip(path):
            return
        self._jobs.enqueue(kind="index", path=str(path), library_folder_id=self._folder_id)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if should_skip(path):
            return
        self._jobs.enqueue(kind="index", path=str(path), library_folder_id=self._folder_id)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        # File no longer exists — can't call should_skip(). Check name only.
        if not _is_video_by_name(path):
            return
        video = self._videos.find_by_path(str(path))
        if video is not None:
            self._videos.update(video.id, status="missing")

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        src = Path(event.src_path)
        dst = Path(event.dest_path)  # type: ignore[attr-defined]
        if _is_video_by_name(src):
            video = self._videos.find_by_path(str(src))
            if video is not None:
                self._videos.update(video.id, status="missing")
        if not should_skip(dst):
            self._jobs.enqueue(kind="index", path=str(dst), library_folder_id=self._folder_id)


class LibraryWatcher:
    def __init__(self, jobs: JobsQueue, videos: VideosRepo) -> None:
        self._jobs = jobs
        self._videos = videos
        self._observer = Observer()
        self._watches: dict[str, object] = {}
        self._status: dict[str, WatchStatus] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join()

    def add_watch(self, folder_id: str, path: str | Path) -> None:
        handler = FolderEventHandler(folder_id, self._jobs, self._videos)
        try:
            watch = self._observer.schedule(handler, str(path), recursive=True)
            with self._lock:
                self._watches[folder_id] = watch
                self._status[folder_id] = WatchStatus(
                    folder_id=folder_id, path=str(path), active=True, error=None,
                )
        except OSError as exc:
            with self._lock:
                self._status[folder_id] = WatchStatus(
                    folder_id=folder_id, path=str(path), active=False,
                    error=f"{exc} — on Linux run: sudo sysctl fs.inotify.max_user_watches=524288",
                )

    def remove_watch(self, folder_id: str) -> None:
        with self._lock:
            watch = self._watches.pop(folder_id, None)
            self._status.pop(folder_id, None)
        if watch is not None:
            self._observer.unschedule(watch)  # type: ignore[arg-type]

    def status(self) -> list[WatchStatus]:
        with self._lock:
            return list(self._status.values())
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/scanning/test_watcher.py -v
```

Expected: all 13 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/scanning/watcher.py tests/scanning/test_watcher.py
git commit -m "feat: implement LibraryWatcher and FolderEventHandler"
```

---

### Task 4: Wire watcher into lifespan, deps, and conftest

**Files:**
- Modify: `src/videosearch/api/app.py`
- Modify: `src/videosearch/api/deps.py`
- Modify: `tests/api/conftest.py`

This task is infrastructure wiring — no new behaviour to test-drive. The verification is that the full test suite still passes after wiring.

- [ ] **Step 1: Add `get_library_watcher` to `deps.py`**

In `src/videosearch/api/deps.py`, add this import at the top with the others:

```python
from videosearch.scanning.watcher import LibraryWatcher
```

Add at the end of the file:

```python
def get_library_watcher(conn: HTTPConnection) -> LibraryWatcher:
    return conn.app.state.library_watcher
```

- [ ] **Step 2: Add `mock_watcher` fixture and override to `tests/api/conftest.py`**

Add the fixture after `mock_downloader`:

```python
@pytest.fixture
def mock_watcher():
    m = MagicMock()
    m.status.return_value = []
    return m
```

Add `mock_watcher` as a parameter to the `client` fixture:

```python
def client(
    test_settings,
    mock_searcher,
    mock_jobs,
    mock_videos,
    mock_frames,
    mock_folders,
    mock_captions,
    mock_broadcaster,
    mock_worker,
    mock_downloader,
    mock_watcher,          # ← add this
):
```

Add the override inside `app.dependency_overrides.update({...})`:

```python
        deps.get_library_watcher: lambda: mock_watcher,
```

- [ ] **Step 3: Wire watcher into `app.py` lifespan**

In `src/videosearch/api/app.py`, inside the `if startup:` block, add after `app.state.broadcaster = broadcaster`:

```python
            from videosearch.scanning.watcher import LibraryWatcher
            watcher = LibraryWatcher(jobs_queue, videos)
            watcher.start()
            for folder in folders.list_all():
                watcher.add_watch(folder.id, folder.path)
            app.state.library_watcher = watcher
```

In the teardown section (after `worker.join(timeout=10)` and before `jobs_queue.close()`), add:

```python
            watcher.stop()
```

The full teardown block becomes:

```python
            if worker is not None:
                worker.stop()
                worker.join(timeout=10)
            watcher.stop()
            jobs_queue.close()
```

- [ ] **Step 4: Run full test suite to verify no regressions**

```bash
uv run pytest tests/ -v
```

Expected: all existing tests pass (the new mock_watcher override prevents any dep-injection errors).

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/app.py src/videosearch/api/deps.py tests/api/conftest.py
git commit -m "feat: wire LibraryWatcher into lifespan and DI"
```

---

### Task 5: Update library router

**Files:**
- Modify: `src/videosearch/api/routers/library.py`
- Modify: `tests/api/test_library.py`

When a folder is registered, start watching it. When deleted, stop watching it.

- [ ] **Step 1: Write failing tests**

Append to `tests/api/test_library.py`:

```python
def test_register_folder_calls_add_watch(client, mock_folders, mock_jobs, mock_watcher, tmp_path):
    folder = tmp_path / "movies"
    folder.mkdir()
    (folder / "a.mp4").write_bytes(b"x" * 200_000)

    client.post("/api/library/folders", json={"path": str(folder)})

    mock_watcher.add_watch.assert_called_once()


def test_delete_folder_calls_remove_watch(client, mock_folders, mock_videos, mock_watcher):
    mock_folders.find_by_id.return_value = _folder("f1")
    mock_videos.list_by_folder.return_value = []

    client.delete("/api/library/folders/f1")

    mock_watcher.remove_watch.assert_called_once_with("f1")
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/api/test_library.py::test_register_folder_calls_add_watch tests/api/test_library.py::test_delete_folder_calls_remove_watch -v
```

Expected: `FAILED` — `AssertionError: Expected 'add_watch' to have been called once.`

- [ ] **Step 3: Update `library.py`**

Replace the imports block at the top of `src/videosearch/api/routers/library.py`:

```python
from videosearch.api.deps import (
    get_jobs_queue,
    get_library_folders_repo,
    get_library_watcher,
    get_videos_repo,
)
from videosearch.scanning.skiplist import should_skip
from videosearch.scanning.watcher import LibraryWatcher
from videosearch.storage.jobs import JobsQueue
from videosearch.storage.library_folders import LibraryFoldersRepo
from videosearch.storage.schemas import LibraryFolderRow
from videosearch.storage.videos import VideosRepo
```

Replace the `register_folder` signature and body:

```python
@router.post("/library/folders", response_model=RegisterFolderResponse)
async def register_folder(
    body: RegisterFolderRequest,
    folders: LibraryFoldersRepo = Depends(get_library_folders_repo),
    jobs: JobsQueue = Depends(get_jobs_queue),
    watcher: LibraryWatcher = Depends(get_library_watcher),
) -> RegisterFolderResponse:
    path = Path(body.path)
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="path is not a directory")

    folder_id = str(uuid.uuid4())
    folder = LibraryFolderRow(id=folder_id, path=str(path), added_at=time.time())
    folders.insert(folder)

    count = await asyncio.to_thread(_walk_and_enqueue, path, folder_id, jobs)
    watcher.add_watch(folder_id, path)
    return RegisterFolderResponse(
        folder=FolderResponse(
            id=folder.id, path=folder.path, added_at=folder.added_at,
            counts=_counts([]),
        ),
        enqueued=count,
    )
```

Replace the `delete_folder` signature and body:

```python
@router.delete("/library/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    purge: bool = False,
    folders: LibraryFoldersRepo = Depends(get_library_folders_repo),
    videos: VideosRepo = Depends(get_videos_repo),
    watcher: LibraryWatcher = Depends(get_library_watcher),
) -> dict:
    folder = folders.find_by_id(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="folder not found")
    if purge:
        for video in videos.list_by_folder(folder_id):
            videos.update(video.id, status="missing")
    watcher.remove_watch(folder_id)
    folders.delete(folder_id)
    return {"ok": True}
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/api/test_library.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/routers/library.py tests/api/test_library.py
git commit -m "feat: call add_watch/remove_watch on folder register/delete"
```

---

### Task 6: Update health endpoint

**Files:**
- Modify: `src/videosearch/api/routers/health.py`
- Modify: `tests/api/test_health.py`

Add `watchers: list[WatcherStatus]` to the health response.

- [ ] **Step 1: Write failing tests**

Append to `tests/api/test_health.py`:

```python
def test_health_includes_watchers_field(client, mock_videos, mock_watcher):
    mock_videos.list_by_status.return_value = []
    mock_watcher.status.return_value = []
    r = client.get("/api/health")
    assert "watchers" in r.json()
    assert isinstance(r.json()["watchers"], list)


def test_health_reports_active_watcher(client, mock_videos, mock_watcher):
    from videosearch.scanning.watcher import WatchStatus
    mock_videos.list_by_status.return_value = []
    mock_watcher.status.return_value = [
        WatchStatus(folder_id="f1", path="/movies", active=True, error=None)
    ]
    r = client.get("/api/health")
    watchers = r.json()["watchers"]
    assert len(watchers) == 1
    assert watchers[0]["folder_id"] == "f1"
    assert watchers[0]["path"] == "/movies"
    assert watchers[0]["active"] is True
    assert watchers[0]["error"] is None


def test_health_reports_inactive_watcher_with_error(client, mock_videos, mock_watcher):
    from videosearch.scanning.watcher import WatchStatus
    mock_videos.list_by_status.return_value = []
    mock_watcher.status.return_value = [
        WatchStatus(folder_id="f1", path="/movies", active=False, error="inotify limit reached")
    ]
    r = client.get("/api/health")
    w = r.json()["watchers"][0]
    assert w["active"] is False
    assert "inotify" in w["error"]
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/api/test_health.py::test_health_includes_watchers_field -v
```

Expected: `FAILED` — `AssertionError: assert 'watchers' in {...}` (field not in response yet).

- [ ] **Step 3: Rewrite `health.py`**

Replace `src/videosearch/api/routers/health.py` with:

```python
from __future__ import annotations

import torch
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from videosearch.api.deps import get_library_watcher, get_videos_repo
from videosearch.scanning.watcher import LibraryWatcher
from videosearch.storage.videos import VideosRepo

router = APIRouter()


class WatcherStatus(BaseModel):
    folder_id: str
    path: str
    active: bool
    error: str | None


class HealthResponse(BaseModel):
    status: str
    db: bool
    models_loaded: bool
    gpu_backend: str
    indexed_count: int
    watchers: list[WatcherStatus]


@router.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    videos: VideosRepo = Depends(get_videos_repo),
    watcher: LibraryWatcher = Depends(get_library_watcher),
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
    watcher_statuses = [
        WatcherStatus(folder_id=s.folder_id, path=s.path, active=s.active, error=s.error)
        for s in watcher.status()
    ]
    return HealthResponse(
        status=status,
        db=db_ok,
        models_loaded=models_loaded,
        gpu_backend=gpu_backend,
        indexed_count=indexed_count,
        watchers=watcher_statuses,
    )
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/api/test_health.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/api/routers/health.py tests/api/test_health.py
git commit -m "feat: add watchers field to health endpoint"
```

---

### Task 7: Config cleanup — remove `library_paths`

**Files:**
- Modify: `src/videosearch/config.py`

`library_paths` was declared in `Settings` for a Docker use case that was dropped. The watcher is now seeded from DB-persisted folders. No test references this field.

- [ ] **Step 1: Remove `library_paths` from `Settings`**

In `src/videosearch/config.py`, remove this line from the `Settings` class:

```python
    library_paths: list[Path] = Field(default_factory=list)
```

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass (no test referenced `library_paths`).

- [ ] **Step 3: Commit and close GitHub issue**

```bash
git add src/videosearch/config.py
git commit -m "chore: remove unused library_paths from Settings"
gh issue close 1 --comment "Implemented in this commit series: watchdog-based watcher, per-folder status in health endpoint, seeded from DB on startup."
```
