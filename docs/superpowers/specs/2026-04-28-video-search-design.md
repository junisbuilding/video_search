# Video Search — Design

**Date:** 2026-04-28
**Status:** Draft (post-brainstorm, pre-implementation plan)

## Goal

A self-hosted web app that indexes videos in user-registered folders and serves
plain-text semantic search over them. A search returns the matching files
grouped together with the specific moments inside each file (timestamps +
thumbnails + captions). Distributed as a `pip`-installable Python package
(`uv tool install` recommended). Primary deploy target: macOS on Apple
Silicon (M3 MacBook Air, 16 GB unified memory). The same package runs on
Linux/WSL with NVIDIA CUDA for development.

## Non-goals (v1)

- LLM-based query expansion (designed for, not built)
- Audio / transcripts (schema-ready, not built)
- Auth, multi-user, sharing, tagging, collections
- Mobile-optimized layout
- CPU-only optimized deployment (works, but not a supported target)
- Docker distribution (deferred to v2; doesn't work on macOS without losing
  GPU acceleration, and is unnecessary for the target user)
- Mac `.app` bundle (current end user is technical; revisit if non-technical
  users adopt it)
- HTTP / remote VLM backend (an interface seam is left for it; no
  implementation in v1)

## Constraints

- Primary deploy: M3 MacBook Air, 16 GB unified memory. All inference runs
  in-process via Apple's Metal backend.
- Dev environment: WSL on Windows with NVIDIA GPU. Identical Python codebase;
  PyTorch and llama-cpp-python both auto-select CUDA.
- Total resident memory at default model sizes ~6–8 GB. Comfortable headroom
  on a 16 GB MBA after macOS overhead.
- Single-user, local network use.
- Library is read-only from the app's perspective; the app never writes
  inside user video folders.

## Architecture

Single Python process, started via the package's `videosearch serve` CLI.
Inside the process:

1. **API/web server** — FastAPI on uvicorn. Serves the SvelteKit frontend
   bundled in the package, exposes JSON endpoints, streams video bytes for
   the player, pushes job progress over WebSocket.
2. **Watcher** — async task in the same event loop. Uses `watchdog` to
   observe registered library folders and enqueues ingest jobs for new /
   changed files, marks deletions.
3. **Indexer** — async task in the same event loop. Pulls jobs from a
   SQLite-backed queue and runs the ingestion pipeline. Blocking work
   (ffmpeg subprocess, model inference) is dispatched to a thread pool via
   `asyncio.run_in_executor`. Both `llama-cpp-python` and PyTorch release
   the GIL during inference, so the API stays responsive while indexing
   runs.
4. **Models** — loaded once at process startup, kept resident:
   - **SigLIP 2** via PyTorch (MPS on Mac, CUDA on Linux)
   - **bge-small** text embedder via sentence-transformers (same backend)
   - **VLM** (Qwen2.5-VL-3B Q4_K_M GGUF + mmproj) via `llama-cpp-python`
     (Metal on Mac, CUDA on Linux). No HTTP server.

A `Captioner` interface wraps the VLM call. v1 ships one implementation
(`LlamaCppCaptioner`). An `HTTPCaptioner` for hitting an OpenAI-compatible
remote endpoint is a small follow-up; it's deferred because the M3 target
makes in-process inference sufficient.

Storage:

- **Vector + metadata DB:** LanceDB (embedded), under the user's data dir.
- **Thumbnails:** flat JPEGs in the same data dir, addressed by
  `(video_id, frame_idx)`.
- **Job queue:** SQLite file in the same data dir.

Why in-process (vs. a separate indexer worker process): unified memory on
Mac means two processes would either double-load the models (~5+ GB extra)
or require shared-memory plumbing. One process avoids both. Crash isolation
is the cost; for a single-user local tool with stable underlying libraries,
that's acceptable.

```
              ┌──────────────────────────────────────────────────┐
              │  videosearch process (Python, asyncio)           │
              │  ┌────────────────────────────────────────────┐  │
~/Movies   →  │  │ FastAPI + Watcher + Indexer (event loop)   │  │
              │  │   ↓                                        │  │
              │  │ thread pool for blocking work              │  │
              │  │   - ffmpeg                                 │  │
              │  │   - SigLIP    (PyTorch + MPS / CUDA)       │  │
              │  │   - VLM       (llama-cpp-python +          │  │
              │  │                Metal / CUDA)               │  │
              │  │   - text embedder                          │  │
              │  └────────────────────────────────────────────┘  │
              │     ↓                                            │
              │  LanceDB / thumbnails / jobs.db   (data dir)     │
              └──────────────────────────────────────────────────┘
                       ↑
                  browser (frontend)
```

## Models

| Role                  | Default                                  | Notes                                                                       |
|-----------------------|------------------------------------------|-----------------------------------------------------------------------------|
| Frame visual embedder | `google/siglip2-base-patch16-256`        | PyTorch + MPS/CUDA. ~600 MB resident. Larger variants swappable.            |
| Caption VLM           | `qwen2.5-vl-3b-instruct` Q4_K_M GGUF     | In-process via `llama-cpp-python`. ~2.5 GB resident incl. mmproj.           |
| Caption text embedder | `BAAI/bge-small-en-v1.5`                 | sentence-transformers + MPS/CUDA. ~150 MB resident.                         |

Models are downloaded on first run from the Hugging Face Hub (or a
user-supplied path) into `~/Library/Application Support/videosearch/models`
on Mac, `~/.local/share/videosearch/models` on Linux. For the VLM, both the
GGUF weights and the matching `mmproj` file are required; the app fetches
both from the same source repo to avoid version mismatch.

## Indexing pipeline

When a video appears in (or is registered into) a watched folder:

1. **Probe & dedupe.** ffprobe metadata. Compute content hash (xxhash of
   first/middle/last MB + duration + size). Skip if hash already in DB.
   Insert `videos` row with `status='pending'`.
2. **Frame sampling.**
   - Uniform: 1 frame/sec via ffmpeg (`-vf fps=1`).
   - Scene detection: PySceneDetect (content-aware) to obtain shot
     boundaries. Used to define captioning windows. Toggleable; on by
     default.
   - Output per frame: a small JPEG thumbnail to disk + an in-memory
     tensor.
3. **Frame embeddings.** Batch frames (default 16 on Mac, 32 on CUDA),
   embed with SigLIP 2 image encoder. Insert into `frame_embeddings`:
   `(video_id, frame_idx, timestamp_sec, embedding, thumb_path)`.
4. **Per-scene captioning.** For each scene window (or fallback fixed
   window of 5–10 s if scene detection is off), pick a representative
   frame (or up to 3 evenly-spaced frames if `mmproj` supports multi-image
   input) and call `Captioner.caption(images, prompt)`. The default
   `LlamaCppCaptioner` invokes the in-process VLM directly. Failures
   (model errors, OOM) surface as retryable errors on the job.
5. **Caption embeddings.** Embed each caption with the text embedder.
   Insert into `caption_embeddings`:
   `(video_id, scene_idx, start_sec, end_sec, caption, embedding)`.
6. **Mark complete.** Update `videos.status='indexed'`, emit a progress
   event.

Failure handling: per-step retry with backoff. On terminal failure, set
`status='failed'` and surface to the UI with a retry action. The schema
permits partial state — frame embeddings without captions are valid;
resumption picks up from the first incomplete step.

Configurable knobs: frame fps, scene detection on/off, VLM model path
(local file or HF repo id), text embedder, max concurrent ingest jobs
(default 1; on Apple Silicon the GPU bandwidth is the bottleneck so 1 is
correct).

## Data model

LanceDB tables (logical schema; concrete columns may add metadata fields):

- `videos`: `id (uuid), path, hash, duration_sec, fps, width, height, mtime,
  status, error, indexed_at`
- `frame_embeddings`: `video_id, frame_idx, timestamp_sec, embedding (vec),
  thumb_path`
- `caption_embeddings`: `video_id, scene_idx, start_sec, end_sec, caption,
  embedding (vec), modality='visual_caption'`
  - The `modality` column is the v2 hook for transcript chunks.
- `library_folders`: `id, path, added_at`
- `jobs` (SQLite, not LanceDB): `id, video_id, kind, status, progress,
  error, created_at, updated_at`

## Search pipeline

1. Frontend POSTs `{ query, k, filters }` to `/api/search`.
2. Server calls `expand_query(text) -> [text]` (identity for v1; LLM hook
   later).
3. For each query string, in parallel:
   - Embed via SigLIP 2 text encoder → `q_image`.
   - Embed via text embedder → `q_text`.
4. Run two ANN searches:
   - `q_image` against `frame_embeddings` (top K, e.g. 200).
   - `q_text` against `caption_embeddings` (top K).
5. Fuse via Reciprocal Rank Fusion. RRF avoids cross-source score-scale
   issues and keeps the fusion weight-free for v1. Replaceable by a learned
   reranker later.
6. Group fused hits by video. Keep the top N moments per video (default 3).
   Sort videos by their best moment score. Return.

Response shape:

```json
{
  "results": [
    {
      "video_id": "...", "path": "...", "duration": 312.4, "best_score": 0.74,
      "moments": [
        {"start": 42.1, "end": 50.0, "score": 0.74,
         "thumb": "/api/videos/.../thumbs/42",
         "caption": "A person opens a red door...",
         "source": "caption"},
        {"start": 187.3, "score": 0.61,
         "thumb": "/api/videos/.../thumbs/187",
         "source": "frame"}
      ]
    }
  ]
}
```

## API surface

- `POST /api/search` — query as above.
- `GET /api/library` — list folders, video counts by status.
- `POST /api/library/folders` — register a folder.
- `DELETE /api/library/folders/{id}` — unregister a folder (preserves
  indexed data unless `?purge=true`).
- `GET /api/jobs` — current and recent jobs with progress.
- `POST /api/jobs/{video_id}/retry` — kick a failed job.
- `GET /api/videos/{id}/stream` — byte-range video stream for the
  in-browser player.
- `GET /api/videos/{id}/thumbs/{frame_idx}` — thumbnail file.
- `GET /api/health` — DB ok, VLM model loaded, GPU backend (MPS / CUDA)
  detected, indexed-count.
- `WS /ws/jobs` — push job progress events to the UI.

## Frontend

SvelteKit, built to static assets, bundled inside the Python package and
served by FastAPI under `/`.

Pages:

1. **Search** (default route) — query input; results grouped by video; each
   group expands to up to 3 matching moments (thumbnail, timestamp,
   caption, score, play). Click play opens an in-page video element seeked
   to `start`.
2. **Library** — list of watched folders, add/remove. Per-folder counts.
   Indexing progress live (WebSocket).
3. **Jobs** — current + recent jobs with per-step progress. Failed jobs
   show the error and a retry button.
4. **Settings** — sampling fps, scene detection toggle, VLM model path,
   embedder choices, read-only data-dir path.

Video player: native `<video>` element against `/api/videos/{id}/stream`
(byte-range). No transcoding in v1; if codec issues appear in practice, an
ffmpeg-based on-the-fly transcode endpoint is a small follow-up.

Out of scope for v1: auth (single-user; document reverse-proxy + basic
auth for LAN exposure), tagging, collections, sharing, multi-user, mobile
flows.

## Configuration

Hierarchy (highest priority last):

1. Code defaults
2. `~/Library/Application Support/videosearch/config.toml` (Mac) or
   `~/.config/videosearch/config.toml` (Linux) — written by the settings UI
3. `VS_*` environment variables
4. CLI flags

Selected env vars:

- `VS_LIBRARY_PATHS` — colon-separated paths the watcher monitors
- `VS_DATA_DIR` — LanceDB + thumbnails + jobs.db (default OS-appropriate)
- `VS_MODELS_DIR` — model cache (default OS-appropriate)
- `VS_VLM_MODEL` — local path *or* HF repo+file id (e.g.
  `bartowski/Qwen2.5-VL-3B-Instruct-GGUF::Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf`)
- `VS_VLM_MMPROJ` — local path *or* HF repo+file id for the mmproj
- `VS_VLM_N_GPU_LAYERS` — default `-1` (all layers on GPU)
- `VS_SIGLIP_MODEL`, `VS_TEXT_EMBEDDER` — HF repo ids
- `VS_FRAME_FPS` — default `1`
- `VS_PORT` — default `8083`

## Installation

### Mac (primary target)

```sh
# one-time system deps
brew install ffmpeg

# install the package
uv tool install video-search

# run
videosearch serve --library ~/Movies
# → http://localhost:8083
```

First launch downloads model files (~3 GB total for SigLIP + bge + Qwen2.5-VL
Q4 + mmproj) into the model cache directory. Subsequent launches are
immediate.

### Linux / WSL (development)

```sh
# system deps
sudo apt install ffmpeg

# install with CUDA-enabled llama-cpp-python wheel
CMAKE_ARGS="-DGGML_CUDA=on" uv tool install video-search

videosearch serve --library /mnt/c/Videos
```

For supported CUDA versions, llama-cpp-python ships pre-built CUDA wheels
that can be installed without recompilation; the app's `pyproject.toml`
documents both routes.

### Process management

The app runs interactively (`videosearch serve`) or under a user-level
service. The package ships:

- A **launchd** plist template for Mac (registered with `videosearch
  install-service` for the partner's machine).
- A **systemd user unit** template for Linux.

Logging: structured JSON to stdout when interactive; rotating logfile under
the data dir when run as a service.

### GPU / acceleration

- **Mac:** PyTorch's MPS backend and llama.cpp's Metal backend are enabled
  automatically. The app fails fast with a clear message if Metal is
  unavailable.
- **Linux:** requires NVIDIA GPU with CUDA 12.x matching the
  `llama-cpp-python` and PyTorch wheels installed. CPU fallback exists but
  is unsupported in v1.

## Testing

- **Unit tests** for indexing-pipeline steps, RRF fusion, config layering,
  and the `expand_query` stub. CPU-only.
- **Integration tests** with stub model implementations (`StubCaptioner`
  returns canned captions; `StubEmbedder` returns deterministic vectors).
  Exercise the full ingest → search loop end-to-end with no model loads.
  Primary guard against integration regressions.
- **Smoke test** with one small video and real models (real SigLIP, real
  Qwen2.5-VL-3B), asserting a known query returns the known video. Runs
  locally on Mac and on the dev Linux box.
- **Frontend** — Playwright covers the search → click → play happy path.

## Roadmap

**v1 (this spec):**

1. Library/folder registration + filesystem watcher
2. Indexing pipeline (frame embeddings + scene captions + caption
   embeddings)
3. Search API with RRF fusion and grouped results
4. Frontend: search, library, jobs, settings
5. `pip` / `uv` package with Mac and Linux/CUDA install paths
6. launchd / systemd service templates
7. Test suites described above

**v2+ (designed for, not built):**

- LLM query expansion (`expand_query` becomes a real call) with API key /
  local-model toggle
- Audio/transcript modality (Whisper → caption-embeddings table with
  `modality='transcript'`)
- HTTP captioner backend (offload inference to a remote VLM via an
  OpenAI-compatible URL — the original "VLM on a Tailscale host" pattern)
- CPU-only supported deployment
- Auth / multi-user
- Tagging, collections, favorites
- Re-ranking / learned fusion weights
- Mobile-optimized layout
- On-the-fly transcoding for codec compatibility
- Mac `.app` bundle (Briefcase / py2app)
- Pre-computed index portability (run indexing on the dev machine, ship
  the LanceDB to the deployed Mac)
- Docker image for Linux server use cases

## Open questions

None blocking implementation. Items to revisit during execution:

- Whether `siglip2-base` is the right default or whether to step up to
  `siglip2-large` / `so400m` based on retrieval-quality testing on Mac
  (more model = more memory + slower indexing).
- Whether default frame fps of 1 is the right balance between recall and
  index size; might end up as a per-library setting.
- Battery-aware indexing: pause ingest while on battery? Default off in
  v1; add a setting if it becomes annoying.
- Concrete `mmproj` / GGUF source: there are several Qwen2.5-VL-3B GGUF
  uploads on Hugging Face. Pick one with both the model weights and the
  matching `mmproj` from the same uploader to avoid version mismatch.
- Does `llama-cpp-python`'s Qwen2.5-VL chat format and multi-image input
  meet our needs for the per-scene captioning prompt? Likely yes; verify
  during early implementation and fall back to single-frame captioning if
  not.
