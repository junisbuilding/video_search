# API Layer — Design

**Date:** 2026-05-01
**Status:** Approved, ready for implementation

## Goal

A FastAPI HTTP server that exposes all backend functionality — search, library
management, ad-hoc ingest, job tracking, video streaming, settings — to the
frontend. A single background thread runs the indexing pipeline. WebSocket
pushes job progress to connected clients. A `videosearch serve` CLI entrypoint
launches everything as one process.

## Architecture

Single Python process. FastAPI on uvicorn. One background worker thread pulls
jobs from `JobsQueue` and runs `index_video()`. Models are loaded once at
startup and kept resident for the lifetime of the process.

```
videosearch serve
  │
  ├─ lifespan (startup)
  │    1. load Settings
  │    2. download/verify + instantiate models (blocks until ready)
  │    3. open Database (LanceDB) + JobsQueue (SQLite)
  │    4. start worker thread
  │
  ├─ FastAPI + uvicorn  (asyncio event loop)
  │    ├─ routers: search, library, jobs, videos, fs, settings, health
  │    └─ WS /ws/jobs  (push from worker thread via run_coroutine_threadsafe)
  │
  └─ worker thread  (synchronous loop)
       while not stop_event:
           job = jobs_queue.claim()
           if job: index_video(...); broadcast progress
           else:   sleep(1)
```

## Tech stack

- **FastAPI** + **uvicorn[standard]** — ASGI server + framework
- **typer** — CLI (`videosearch serve`)
- **python-multipart** — form parsing (folder picker path submission)
- `watchdog` deferred to the filesystem watcher phase

## File structure

```
src/videosearch/
  api/
    __init__.py
    app.py          # create_app() factory + lifespan context manager
    deps.py         # Depends() functions: get_searcher, get_jobs_queue, …
    worker.py       # IndexerWorker: threading.Thread subclass
    ws.py           # WebSocket broadcaster (thread→async bridge)
    routers/
      __init__.py
      search.py
      library.py
      jobs.py
      videos.py
      fs.py
      settings.py
      health.py
  cli.py            # typer app; `videosearch serve` console script
```

## Lifespan

`app.py` exports `create_app(settings: Settings) -> FastAPI`. The lifespan
context manager:

1. Instantiates `SigLIPEmbedder`, `BGEEmbedder`, `LlamaCppCaptioner` (models
   are downloaded from HF Hub on first run, cached in `settings.models_dir`,
   loaded from disk on subsequent runs — no re-download).
2. Opens `Database(settings.data_dir)` and `JobsQueue(settings.data_dir / "jobs.db")`.
3. Constructs `Searcher`, `VideosRepo`, `FrameEmbeddingsRepo`,
   `CaptionEmbeddingsRepo`, `LibraryFoldersRepo`.
4. Starts `IndexerWorker` thread.
5. Yields — server begins accepting requests.
6. On shutdown: sets `stop_event`, joins worker thread, closes DB connections.

All shared state lives on `app.state`. `deps.py` exposes one `Depends()`
function per resource (e.g. `get_searcher`, `get_jobs_queue`), reading from
`request.app.state`. This makes every route handler independently testable via
FastAPI's dependency override mechanism.

## Background worker

`worker.py` — `IndexerWorker(threading.Thread)`:

```python
while not self._stop.is_set():
    job = self._jobs.claim()
    if job is None:
        self._stop.wait(timeout=1.0)
        continue
    try:
        self._jobs.update_progress(job.id, 0.0)
        self._broadcast(job, "in_progress", 0.0)
        index_video(
            path=Path(video_row.path),
            videos=self._videos,
            frames=self._frames,
            captions=self._captions,
            image_embedder=self._image_embedder,
            text_embedder=self._text_embedder,
            captioner=self._captioner,
            work_dir=self._work_dir,
        )
        self._jobs.complete(job.id)
        self._broadcast(job, "completed", 1.0)
    except Exception as e:
        self._jobs.fail(job.id, error=str(e))
        self._broadcast(job, "failed", 0.0, error=str(e))
```

`_broadcast` calls `asyncio.run_coroutine_threadsafe(ws.send_all(event), loop)`
— fire-and-forget from the worker thread into the asyncio event loop.

## WebSocket broadcaster (`ws.py`)

```python
class JobBroadcaster:
    def __init__(self, loop: asyncio.AbstractEventLoop): ...
    def register(self, ws: WebSocket) -> None: ...
    def unregister(self, ws: WebSocket) -> None: ...
    async def send_all(self, event: dict) -> None:
        # sends to all registered clients; removes any that raise on send
    def broadcast(self, event: dict) -> None:
        # sync entry point for worker thread
        asyncio.run_coroutine_threadsafe(self.send_all(event), self._loop)
```

`WS /ws/jobs` handler:
1. Accepts the connection, registers with `JobBroadcaster`.
2. Sends a snapshot of all active + recent jobs (so client starts with current state).
3. Waits indefinitely, catches `WebSocketDisconnect`, unregisters.

## Endpoints

### Search

**`POST /api/search`**
```json
// request
{"query": "string", "k": 10, "include_missing": false}

// response
{
  "query": "string",
  "results": [
    {
      "video_id": "uuid",
      "path": "/abs/path/to/file.mp4",
      "duration_sec": 312.4,
      "top_score": 0.74,
      "moments": [
        {
          "timestamp_sec": 42.1,
          "score": 0.74,
          "thumb_url": "/api/videos/{id}/thumbs/{frame_idx}",
          "caption": "A person opens a red door.",
          "source": "caption"
        }
      ]
    }
  ]
}
```

`include_missing=false` (default) filters out videos with `status='missing'`.
The server joins `SearchResponse` moments with `VideoRow` to add `path` and
`duration_sec`. `thumb_url` is constructed server-side from `thumb_path`.

### Library

**`GET /api/library`**
```json
{
  "folders": [
    {
      "id": "uuid", "path": "/abs/path", "added_at": 1234567890.0,
      "counts": {"indexed": 42, "pending": 3, "failed": 1, "missing": 0}
    }
  ],
  "ad_hoc_counts": {"indexed": 5, "pending": 0, "failed": 0, "missing": 2}
}
```

**`POST /api/library/folders`** — body `{"path": "/abs/path"}`
Validates the path exists and is a directory. Inserts a `LibraryFolderRow`.
Walks the folder recursively (applying skip-list), enqueues one job per
discovered video. Returns the new folder record + count of enqueued jobs.

**`DELETE /api/library/folders/{id}`** — `?purge=true` deletes embeddings +
thumbnails + video rows for all videos in the folder. Default preserves data.

**`POST /api/library/folders/{id}/rescan`** — re-walks the folder and enqueues
any videos not currently `indexed`. Returns count of newly-enqueued jobs.

### Ad-hoc ingest

**`POST /api/ingest`** — body `{"path": "/abs/path", "recursive": false}`
Accepts a single file or directory. If a directory and `recursive=true`, walks
it (skip-list applied). Enqueues each discovered video. `library_folder_id`
is `null` for all ad-hoc jobs. Returns `{"enqueued": [job_id, ...]}`.

### Jobs

**`GET /api/jobs`** — returns up to 200 most recent jobs across all statuses,
ordered by `created_at` descending. Requires adding a `list_recent(limit)` method
to `JobsQueue` (existing `list_by_status` only queries one status at a time).
```json
{"jobs": [{"id": "uuid", "video_id": "uuid", "kind": "index", "status": "in_progress",
            "progress": 0.4, "error": null, "created_at": 1234.0, "updated_at": 1235.0}]}
```

**`POST /api/jobs/{job_id}/retry`** — re-enqueues a `failed` job. Returns 409
if the job is not in `failed` status.

### Videos

**`GET /api/videos/{id}/stream`** — byte-range streaming from the file at
`VideoRow.path`. Returns 404 if video not found, 410 if `status='missing'`.
Sets `Accept-Ranges: bytes` and handles `Range` headers for seeking.

**`GET /api/videos/{id}/thumbs/{frame_idx}`** — serves the JPEG at
`FrameEmbeddingRow.thumb_path`. Returns 404 if not found.

**`POST /api/videos/{id}/reveal`** — opens the enclosing folder in the OS file
manager:
- macOS: `open -R <path>`
- Linux: `xdg-open <parent_dir>`

Returns 200 on success, 501 if no display is available (`$DISPLAY` / `$WAYLAND_DISPLAY`
not set on Linux), 404 if the video row doesn't exist.

### Filesystem picker

**`GET /api/fs/list?path=<abs_path>`** — directory listing for the folder
picker. Defaults to `$HOME` if `path` is omitted. Path traversal check:
resolves symlinks, rejects paths outside `$HOME` (returns 403). Never writes.

```json
{
  "path": "/abs/path",
  "parent": "/abs",
  "entries": [
    {"name": "Movies", "path": "/abs/path/Movies", "kind": "dir",
     "size_bytes": null, "mtime": 1234567890.0},
    {"name": "clip.mp4", "path": "/abs/path/clip.mp4", "kind": "video",
     "size_bytes": 52428800, "mtime": 1234567890.0}
  ]
}
```

`kind` is `"dir"`, `"video"` (extension matches skip-list allowlist), or
`"other"`. Hidden files (`.`-prefixed) are excluded.

### Settings

**`GET /api/settings`** → current `Settings` object as JSON (all fields,
including computed defaults).

**`PATCH /api/settings`** — partial update. Accepts any subset of `Settings`
fields. Writes changed keys to `config.toml` in `settings.data_dir`. Fields
that affect model loading (`siglip_model`, `text_embedder`, `vlm_model`,
`vlm_mmproj`) take effect on next restart; safe fields (`frame_fps`,
`scene_detection`, `port`) take effect immediately. Returns the updated
settings object.

### Health

**`GET /api/health`**
```json
{
  "status": "ok",
  "db": true,
  "models_loaded": true,
  "gpu_backend": "mps",
  "indexed_count": 47
}
```

`status` is `"degraded"` if any of `db` or `models_loaded` is false.
`gpu_backend` is `"mps"` (Mac), `"cuda"` (Linux with GPU), or `"cpu"`.

## CLI

`cli.py` — typer app registered as `videosearch = videosearch.cli:app` in
`pyproject.toml` under `[project.scripts]`.

```
videosearch serve [--port INT] [--config PATH] [--data-dir PATH] [--models-dir PATH]
```

CLI flags override `VS_*` env vars which override `config.toml` which override
field defaults. `data_dir` is resolved from CLI/env first; `config.toml` is then
read from `data_dir / "config.toml"` so the path is always deterministic.
The `serve` command: builds `Settings`, calls `create_app()`,
runs `uvicorn.run(app, host="127.0.0.1", port=settings.port)`.

## Skip-list (for folder walks)

Applied during `POST /api/library/folders`, `POST /api/library/folders/{id}/rescan`,
and `POST /api/ingest`. Implemented as a pure function in
`src/videosearch/scanning/skiplist.py` (already exists). Default-skipped:

- Hidden files and directories (name starts with `.`)
- Known metadata: `.DS_Store`, `Thumbs.db`
- Bundle directories: `*.photoslibrary`, `*.app`, `*.framework`
- Files smaller than 100 KB
- Extensions not in the video allowlist: `.mp4 .mkv .mov .avi .webm .m4v .wmv .mpg .mpeg .3gp .flv .ts`

## Testing

- **Unit tests** for `worker.py` (mock `JobsQueue` + `index_video`), `ws.py`
  (mock WebSocket), `fs.py` router (path traversal checks), `settings.py`
  router (config.toml write/read round-trip).
- **Integration tests** using FastAPI's `TestClient` with dependency overrides
  to inject stub models and an in-memory/tmp DB. Covers the full
  search → response shape, library registration → job enqueued, job retry
  flow.
- No Playwright in this phase (frontend not yet built).

## New dependencies

Add to `pyproject.toml`:
```toml
"fastapi>=0.111",
"uvicorn[standard]>=0.29",
"typer>=0.12",
"python-multipart>=0.0.9",
```
