# Video Search — Design

**Date:** 2026-04-28
**Status:** Draft (post-brainstorm, pre-implementation plan)

## Goal

A self-hosted web app that indexes videos in user-registered folders and serves
plain-text semantic search over them. A search returns the matching files
grouped together with the specific moments inside each file (timestamps +
thumbnails + captions). Distributed as a Docker image.

## Non-goals (v1)

- LLM-based query expansion (designed for, not built)
- Audio / transcripts (schema-ready, not built)
- Auth, multi-user, sharing, tagging, collections
- Mobile-optimized layout
- CPU-only optimized deployment (works, but not a supported target)
- Python package distribution

## Constraints

- App container targets a machine with one NVIDIA GPU. The local GPU only
  runs SigLIP 2 (frame embedding) and the text embedder — together ~2 GB
  VRAM at default model sizes, comfortable on a 4 GB GPU.
- The VLM (caption generator) runs as a separate service, reached over HTTP
  at any URL configured by the user — the same host, a separate LAN box, a
  Tailscale node, anywhere routable. The app does not assume the VLM runs
  locally and does not manage its lifecycle. Default model `qwen2.5-vl-3b`
  fits in ≤12 GB VRAM on whichever host serves it.
- Single-user, local network use
- Library is read-only from the app's perspective; the app never writes inside
  user video folders

## Architecture

Single Docker image, started via `docker compose up`. Inside the container:

1. **API/web server** — FastAPI. Serves the SvelteKit frontend, exposes JSON
   endpoints, streams video bytes for the player, pushes job progress over
   WebSocket.
2. **Watcher** — async task in the API process. Uses `watchdog` to observe
   registered library folders and enqueues ingest jobs for new/changed files,
   marks deletions.
3. **Indexer worker** — separate process in the same image. Pulls jobs from a
   SQLite-backed queue, runs the ingestion pipeline. Single worker process; GPU
   concurrency comes from batching, not parallelism.
4. **External VLM service** — any OpenAI-compatible chat-completions endpoint
   that supports vision input (llama-server, vLLM, Ollama, a hosted endpoint,
   etc.). Reached over HTTP at `VS_VLM_ENDPOINT`. Could be the same host, a
   separate machine on the LAN, a Tailscale node, or any routable URL. The app
   does not start, supervise, or co-locate this service. Users without one can
   optionally run llama-server as a compose sidecar (example below).

Storage:

- **Vector + metadata DB:** LanceDB (embedded). One mounted volume.
- **Thumbnails:** flat JPEGs on the same volume, addressed by
  `(video_id, frame_idx)`.
- **Job queue:** SQLite file on the same volume.

Why one image with multiple processes (vs. multiple images): simpler
distribution, shared model cache, GPU is the bottleneck so multi-process
scaling buys little. Components communicate via DB and queue (not in-memory
state), so splitting later is straightforward.

```
            ┌─────────────────────────────────────┐
            │  Docker container: video-search     │
            │  ┌──────────┐    ┌──────────────┐  │
host vols → │  │FastAPI + │←→  │ Indexer      │  │     VLM endpoint
~/Videos    │  │Watcher   │ q  │ worker proc  │──┼──→  (any reachable URL:
./data      │  └────┬─────┘    └──────┬───────┘  │      same host, LAN box,
./models    │       │                 │          │      Tailscale, etc.)
            │     LanceDB ←───────────┘          │
            │     thumbnails/                    │
            │     jobs.db                        │
            └────────────────────────────────────┘
                  ↑
              browser (frontend)
```

## Models

| Role                  | Default                                      | Notes                                                                |
|-----------------------|----------------------------------------------|----------------------------------------------------------------------|
| Frame visual embedder | `google/siglip2-base-patch16-256`            | Image-text contrastive. ~600 MB VRAM. Larger variants swappable.     |
| Caption VLM           | user-provided OpenAI-compatible endpoint     | Default model name `qwen2.5-vl-3b`. Endpoint URL is required config — no default host assumed. |
| Caption text embedder | `BAAI/bge-small-en-v1.5`                     | Embeds VLM-generated captions for the text retrieval index.          |

All three are configurable. The two locally-run models (SigLIP 2 + text
embedder) together fit in ~2 GB of VRAM. The VLM is on whichever host the
user points the endpoint at; default model `qwen2.5-vl-3b` fits in ≤12 GB
VRAM on that host.

## Indexing pipeline

When a video appears in (or is registered into) a watched folder:

1. **Probe & dedupe.** ffprobe metadata. Compute content hash (xxhash of
   first/middle/last MB + duration + size). Skip if hash already in DB. Insert
   `videos` row with `status='pending'`.
2. **Frame sampling.**
   - Uniform: 1 frame/sec via ffmpeg (`-vf fps=1`).
   - Scene detection: PySceneDetect (content-aware) to obtain shot boundaries.
     Used to define captioning windows. Toggleable; on by default.
   - Output per frame: a small JPEG thumbnail to disk + an in-memory tensor.
3. **Frame embeddings.** Batch frames (default batch size 32), embed with
   SigLIP 2 image encoder. Insert into `frame_embeddings`:
   `(video_id, frame_idx, timestamp_sec, embedding, thumb_path)`.
4. **Per-scene captioning.** For each scene window (or fallback fixed window of
   5–10 s if scene detection is off), pick a representative frame (or up to 3
   evenly-spaced frames if the VLM accepts multi-image input) and POST to the
   VLM's OpenAI-compatible `/v1/chat/completions` endpoint with a captioning
   prompt. Endpoint URL and model name come from config; the app treats this
   as a black-box HTTP call. Network failures surface as retryable errors on
   the job.
5. **Caption embeddings.** Embed each caption with the text embedder. Insert
   into `caption_embeddings`:
   `(video_id, scene_idx, start_sec, end_sec, caption, embedding)`.
6. **Mark complete.** Update `videos.status='indexed'`, emit a progress event.

Failure handling: per-step retry with backoff. On terminal failure, set
`status='failed'` and surface to the UI with a "retry" action. The schema
permits partial state — frame embeddings without captions are valid; resumption
picks up from the first incomplete step.

Configurable knobs: frame fps, scene detection on/off, VLM endpoint and model
name, text embedder, max concurrent ingest jobs (default 1).

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
5. Fuse via Reciprocal Rank Fusion. RRF avoids cross-source score-scale issues
   and keeps the fusion weight-free for v1. Replaceable by a learned reranker
   later.
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
- `DELETE /api/library/folders/{id}` — unregister a folder (preserves indexed
  data unless `?purge=true`).
- `GET /api/jobs` — current and recent jobs with progress.
- `POST /api/jobs/{video_id}/retry` — kick a failed job.
- `GET /api/videos/{id}/stream` — byte-range video stream for the in-browser
  player.
- `GET /api/videos/{id}/thumbs/{frame_idx}` — thumbnail file.
- `GET /api/health` — DB ok, VLM endpoint reachable, GPU detected,
  indexed-count.
- `WS /ws/jobs` — push job progress events to the UI.

## Frontend

SvelteKit, served as static assets by FastAPI under `/`.

Pages:

1. **Search** (default route) — query input; results grouped by video; each
   group expands to up to 3 matching moments (thumbnail, timestamp, caption,
   score, play). Click play opens an in-page video element seeked to `start`.
2. **Library** — list of watched folders, add/remove. Per-folder counts.
   Indexing progress live (WebSocket).
3. **Jobs** — current + recent jobs with per-step progress. Failed jobs show
   the error and a retry button.
4. **Settings** — sampling fps, scene detection toggle, VLM endpoint/model,
   embedder choices, read-only storage path.

Video player: native `<video>` against `/api/videos/{id}/stream` (byte-range).
No transcoding in v1; if codec issues appear in practice, an ffmpeg-based
on-the-fly transcode endpoint is a small follow-up.

Out of scope for v1: auth (single-user; document reverse-proxy + basic auth
for LAN exposure), tagging, collections, sharing, multi-user, mobile flows.

## Configuration

Hierarchy (highest priority last):

1. Code defaults
2. `/data/config.toml` — written by the settings UI
3. `VS_*` environment variables
4. CLI flags (dev only)

Selected env vars:

- `VS_LIBRARY_PATHS` — colon-separated mount points the watcher monitors
- `VS_DATA_DIR` — LanceDB + thumbnails + jobs.db
- `VS_MODELS_DIR` — model cache
- `VS_VLM_ENDPOINT`, `VS_VLM_MODEL`
- `VS_SIGLIP_MODEL`, `VS_TEXT_EMBEDDER`
- `VS_FRAME_FPS` (default 1)

## Docker & deployment

- Base image: `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04` (or matching CUDA
  for the host). System deps: ffmpeg, python 3.12, git.
- Models cached in `/models` (mounted volume).
- Entrypoint launches FastAPI + the indexer worker. `--no-watcher`,
  `--no-worker` flags for debugging.
- App port: **8083** (`8083:8083`).
- GPU is required at runtime; the app fails fast with a clear message if no
  GPU is detected (no silent CPU fallback).
- Library mount is read-only.
- The VLM endpoint is required user config — the app does not ship a default
  host. Users point `VS_VLM_ENDPOINT` at any reachable OpenAI-compatible
  chat-completions URL.

### Default compose (VLM is remote)

This is the expected primary deployment. The VLM lives on another machine —
LAN box, GPU server, Tailscale node, hosted endpoint, etc. The app container
just needs to be able to reach it.

```yaml
services:
  videosearch:
    image: ghcr.io/<user>/video-search:latest
    ports: ["8083:8083"]
    volumes:
      - ~/Videos:/library:ro
      - ./data:/data
      - ./models:/models
    environment:
      - VS_LIBRARY_PATHS=/library
      - VS_DATA_DIR=/data
      - VS_MODELS_DIR=/models
      - VS_VLM_ENDPOINT=http://vlm-host.tailnet.example:8080
      - VS_VLM_MODEL=qwen2.5-vl-3b
      - VS_SIGLIP_MODEL=google/siglip2-base-patch16-256
      - VS_TEXT_EMBEDDER=BAAI/bge-small-en-v1.5
      - VS_FRAME_FPS=1
    deploy:
      resources:
        reservations:
          devices:
            - { driver: nvidia, count: 1, capabilities: [gpu] }
```

For a host-run dev VLM (llama-server on the same machine), set
`VS_VLM_ENDPOINT=http://host.docker.internal:8080`.

### Optional: co-located VLM sidecar

Provided as a convenience pattern for users without a separate VLM host. Not
the primary supported path.

```yaml
services:
  videosearch:
    # ...as above, but:
    environment:
      - VS_VLM_ENDPOINT=http://llama-server:8080
      # ...

  llama-server:
    image: ghcr.io/ggml-org/llama.cpp:server-cuda
    command:
      ["-m", "/models/qwen2.5-vl-3b.gguf",
       "--mmproj", "/models/mmproj.gguf",
       "--port", "8080"]
    volumes: [./models:/models]
    deploy:
      resources:
        reservations:
          devices:
            - { driver: nvidia, count: 1, capabilities: [gpu] }
```

Logging: structured JSON to stdout. `docker logs` is the supported interface.

## Testing

- **Unit tests** for indexing-pipeline steps, RRF fusion, config layering, and
  the `expand_query` stub. CPU-only.
- **Integration tests** that spin up FastAPI with a stub VLM (returns canned
  captions) and a stub embedder (returns deterministic vectors). Exercise the
  full ingest → search loop end-to-end without a GPU. This is the primary
  guard against integration regressions.
- **Smoke test** in the real Docker image with one small video, real SigLIP,
  and a real VLM endpoint, asserting a known query returns the known video.
  Runs in CI on a GPU runner where available; otherwise local-only.
- **Frontend** — Playwright covers the search → click → play happy path.

## Roadmap

**v1 (this spec):**

1. Library/folder registration + filesystem watcher
2. Indexing pipeline (frame embeddings + scene captions + caption embeddings)
3. Search API with RRF fusion and grouped results
4. Frontend: search, library, jobs, settings
5. Docker image + compose example
6. Test suites described above

**v2+ (designed for, not built):**

- LLM query expansion (`expand_query` becomes a real call) with API key /
  local-model toggle
- Audio/transcript modality (Whisper → caption-embeddings table with
  `modality='transcript'`)
- CPU-only supported deployment
- Auth / multi-user
- Tagging, collections, favorites
- Re-ranking / learned fusion weights
- Mobile-optimized layout
- On-the-fly transcoding for codec compatibility

## Open questions

None blocking implementation. Items to revisit during execution:

- Whether `siglip2-base` is the right default or whether to step up to
  `siglip2-large` / `so400m` based on retrieval-quality testing.
- Whether default frame fps of 1 is the right balance between recall and
  index size; might end up as a per-library setting.
- Whether in-process indexer worker (vs. separate process) is acceptable for
  v1 simplicity; the design assumes separate process for crash isolation.
