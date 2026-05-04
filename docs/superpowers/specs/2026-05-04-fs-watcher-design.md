# Filesystem Watcher — Design

**Date:** 2026-05-04
**Status:** Approved, ready for implementation
**GitHub issue:** #1

## Goal

Add a `watchdog`-based filesystem watcher so that new, modified, and deleted video files in registered library folders are detected automatically — without requiring manual rescans.

## Architecture

A single `watchdog.observers.Observer` instance runs in its own background thread (one thread total, regardless of how many folders are watched). A `LibraryWatcher` class wraps the observer and holds one `FolderEventHandler` per registered library folder. Event handlers call `JobsQueue` and `VideosRepo` directly on the watchdog thread — `JobsQueue` uses SQLite (`check_same_thread=False`) and `VideosRepo` uses LanceDB (already called from `IndexerWorker`'s thread), so both are safe without asyncio bridging.

The watcher is created in the FastAPI lifespan alongside existing state (jobs queue, repos), seeded with all folders already in the DB, and torn down on shutdown.

## File structure

```
src/videosearch/
  scanning/
    watcher.py          # New: LibraryWatcher + FolderEventHandler
  storage/
    videos.py           # Add find_by_path()
  api/
    app.py              # Start/stop watcher in lifespan; seed from DB
    deps.py             # Add get_library_watcher()
    routers/
      library.py        # Call add_watch / remove_watch on register / delete
      health.py         # Add watchers: list[WatchStatus] to response
  config.py             # Remove unused library_paths field
pyproject.toml          # Add watchdog>=4.0
```

## `watcher.py`

### `WatchStatus`

```python
@dataclass(frozen=True)
class WatchStatus:
    folder_id: str
    path: str
    active: bool
    error: str | None
```

### `FolderEventHandler`

Subclass of `watchdog.events.FileSystemEventHandler`. Constructed with `folder_id`, `jobs: JobsQueue`, `videos: VideosRepo`.

| Event | Condition | Action |
|-------|-----------|--------|
| `on_created` | file (not dir), not on skiplist | `jobs.enqueue(kind="index", path=..., library_folder_id=...)` |
| `on_modified` | file (not dir), not on skiplist | `jobs.enqueue(kind="index", path=..., library_folder_id=...)` |
| `on_deleted` | file (not dir), not on skiplist | `videos.find_by_path(path)` → `videos.update(id, status="missing")` if found |
| `on_moved` | file (not dir) | mark `src_path` missing; enqueue `dest_path` if not on skiplist |

Directory events are ignored in all handlers (`event.is_directory` check).

### `LibraryWatcher`

```python
class LibraryWatcher:
    def __init__(self, jobs: JobsQueue, videos: VideosRepo): ...
    def start(self) -> None: ...        # observer.start()
    def stop(self) -> None: ...         # observer.stop(); observer.join()
    def add_watch(self, folder_id: str, path: str | Path) -> None: ...
    def remove_watch(self, folder_id: str) -> None: ...
    def status(self) -> list[WatchStatus]: ...
```

`add_watch` wraps `observer.schedule(handler, path, recursive=True)` in a try/except. On `OSError` (e.g. inotify limit on Linux), stores `WatchStatus(active=False, error=<message>)` instead of raising. All mutations to `_watches` and `_status` are protected by a `threading.Lock`.

`remove_watch` calls `observer.unschedule(watch)` and removes from internal dicts.

## `VideosRepo.find_by_path`

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

## Lifespan changes (`app.py`)

After constructing `folders`, `jobs_queue`, and `videos`:

```python
from videosearch.scanning.watcher import LibraryWatcher

watcher = LibraryWatcher(jobs_queue, videos)
watcher.start()
for folder in folders.list_all():
    watcher.add_watch(folder.id, folder.path)
app.state.library_watcher = watcher
```

On shutdown (after worker is stopped):

```python
watcher.stop()
```

## DI (`deps.py`)

```python
def get_library_watcher(conn: HTTPConnection) -> LibraryWatcher:
    return conn.app.state.library_watcher
```

## Library router changes

Both routes inject `watcher: LibraryWatcher = Depends(get_library_watcher)`.

`POST /library/folders` — after initial walk:
```python
watcher.add_watch(folder_id, path)
```

`DELETE /library/folders/{id}` — before DB delete:
```python
watcher.remove_watch(folder_id)
```

## Health endpoint changes

New fields on `HealthResponse`:

```python
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
```

If `app.state` has no `library_watcher` (e.g. tests with `startup=False`), return `watchers: []`.

On inotify limit hit, the error string is:
```
inotify watch limit reached — run: sudo sysctl fs.inotify.max_user_watches=524288
To make permanent: echo fs.inotify.max_user_watches=524288 | sudo tee /etc/sysctl.d/99-inotify.conf
```

## Config cleanup

Remove `library_paths: list[Path]` from `Settings`. Update any tests that reference it.

## Dependency

Add to `pyproject.toml` dependencies:
```
"watchdog>=4.0",
```

## Testing

- `tests/scanning/test_watcher.py` — unit tests using a real temp directory:
  - `add_watch` → file created in dir → job enqueued
  - `add_watch` → file modified → job enqueued
  - `add_watch` → file deleted → video marked missing
  - `add_watch` → file moved → old path missing, new path enqueued
  - skiplist files (dotfiles, non-video extensions) → no job enqueued
  - `remove_watch` → no further events processed
  - `OSError` on `schedule` → `status()` shows `active=False` with error string
- `tests/storage/test_videos.py` — add test for `find_by_path`
- `tests/api/test_health.py` — health endpoint includes `watchers` list
- `tests/api/test_library.py` — register folder calls `add_watch`; delete folder calls `remove_watch`

## Out of scope

- `VS_LIBRARY_PATHS` env var (removed — DB-persisted folders are sufficient)
- Download throttling or priority
- Docker distribution
- Remote/network filesystem support
- Polling fallback for network drives
