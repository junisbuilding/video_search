# Frontend UI — Design

**Date:** 2026-05-02
**Status:** Approved, ready for implementation

## Goal

A SvelteKit single-page application that gives the user a search-first interface for their local video library. Search is the entry point; library management, job monitoring, and settings are secondary pages reachable via a top navbar.

## Architecture

SvelteKit with `@sveltejs/adapter-static` compiles the app to plain HTML/JS/CSS. The build output lands in `src/videosearch/static/`, which is committed to the repository and included in the Python package — end users need no Node.js at runtime.

FastAPI gains two additions in `app.py`:
1. `StaticFiles` mounted at `/` serving `src/videosearch/static/`
2. A catch-all `GET /{path:path}` route that returns `index.html` for any path not matched by the API, enabling SvelteKit's client-side router.

During development, `npm run dev` starts a Vite dev server on port 5173. `vite.config.ts` proxies `/api` and `/ws` to `localhost:8083`, so the FastAPI server runs independently.

```
video_search/
  frontend/                      ← SvelteKit project (Node.js toolchain)
    src/
      lib/
        api.ts                   ← typed fetch wrappers for every API endpoint
        stores.ts                ← Svelte stores: searchResults, activeVideo, jobs
        ws.ts                    ← WebSocket client; feeds the jobs store
      lib/components/
        MomentCard.svelte
        MomentGrid.svelte
        VideoPlayer.svelte
        FolderPicker.svelte      ← filesystem picker modal dialog
        JobItem.svelte
      routes/
        +layout.svelte           ← top navbar, global styles, WS init
        +page.svelte             ← Search page
        library/+page.svelte
        jobs/+page.svelte
        settings/+page.svelte
    svelte.config.js             ← adapter-static, no SSR
    vite.config.ts               ← proxy /api and /ws → localhost:8083 in dev
    package.json
    vitest.config.ts
  src/videosearch/
    static/                      ← build output; served by FastAPI; committed
    api/app.py                   ← gains StaticFiles mount + SPA fallback route
```

## Visual design

- **Theme:** dark background (`#0d0d0d`), surface cards (`#1a1a1a`), borders (`#1e1e1e`–`#2a2a2a`), primary text (`#e0e0e0`), accent (`#4ade80` — green).
- **Typography:** system monospace stack for the logo/nav; system sans-serif for body text.
- **Accent usage:** timestamps, active nav item underline, selected card border, primary buttons, progress bar fill, search result count.

## Navigation

A slim top navbar is present on every page:

```
[ ■ VIDEOSEARCH ]   Search   Library   Jobs   Settings
```

The active page is underlined in green. The logo is non-clickable (the user is always one nav click away from anywhere).

## Pages

### Search (default route `/`)

**Empty state:** the search bar is centred vertically on the screen. Below it, a muted line shows the total indexed moment count (e.g. "247 moments across 18 videos") pulled from `GET /api/health`.

**After search:** the layout splits into two columns:

- **Left column (240 px fixed):** a scrollable flat grid of `MomentCard` components, one per matching moment. Each card shows: the frame thumbnail (fetched from `/api/videos/{id}/thumbs/{frame_idx}`), the timestamp in green, the caption, and the filename in muted text. The selected card has a green border.
- **Right column (flex):** the `VideoPlayer` component. The HTML5 `<video>` element is sourced from `/api/videos/{id}/stream` and seeks to the matched timestamp when a card is clicked. Below the video: filename, caption, and a "Reveal" button (`POST /api/videos/{id}/reveal`).

Clicking any card updates `activeVideo` and the player seeks immediately. The result count appears beneath the search bar ("4 moments found").

### Library (`/library`)

A list of registered folders. Each row shows: folder path, indexed/pending/failed/missing counts, a "Rescan" button, and a "Remove" button (with confirmation). An "Add Folder" button in the top-right opens the `FolderPicker` modal.

**FolderPicker modal:** calls `GET /api/fs/list?path=…` on each navigation step. Displays the current path, a list of subdirectories and video files with icons, and a breadcrumb trail. "Add this folder" calls `POST /api/library/folders` and closes the modal; the folder appears in the list immediately with a pending count reflecting the enqueued jobs.

### Jobs (`/jobs`)

A reverse-chronological list of recent jobs (from `GET /api/jobs`), updated in real time via the WebSocket store. Each `JobItem` shows: filename (or path), status badge, a progress bar (for in-progress jobs), an error message (for failed jobs), and a "Retry" button that calls `POST /api/jobs/{id}/retry`. Completed jobs show a green checkmark.

The WebSocket connection (`ws://host/ws/jobs`) is established once in `+layout.svelte` on mount and reconnects automatically on disconnect. Each event is an `upsert` into the `jobs` store keyed by job ID.

### Settings (`/settings`)

A form bound to the fields returned by `GET /api/settings`. Submitting calls `PATCH /api/settings` with only the changed fields (tracked via `model_fields_set` equivalent on the client: only fields the user has touched are sent). Fields:

| Field | Input type | Notes |
|---|---|---|
| `frame_fps` | number (step 0.5) | Frames extracted per second |
| `scene_detection` | checkbox | Enable scene-change detection |
| `port` | number | Server port (requires restart) |
| `siglip_model` | text | HuggingFace model ID |
| `text_embedder` | text | HuggingFace model ID |
| `vlm_model` | text | GGUF path or HF repo |
| `vlm_mmproj` | text | mmproj path |
| `vlm_n_gpu_layers` | number | -1 = all layers on GPU |

Fields that require a restart (port, model paths) are annotated with a muted "⚠ requires restart" hint.

## State management

Three Svelte stores cover all runtime state:

```typescript
// stores.ts
export const searchResults = writable<SearchResponse | null>(null);
export const activeVideo = writable<{ videoId: string; frameIdx: number; timestamp: number } | null>(null);
export const jobs = writable<Job[]>([]);
```

`searchResults` is set on each search submit. `activeVideo` is set when the user clicks a `MomentCard`; `VideoPlayer` subscribes to it and seeks. The `jobs` store is fed by the WebSocket client:

```typescript
// ws.ts
export function connectJobsSocket() {
  const ws = new WebSocket(`ws://${location.host}/ws/jobs`);
  ws.onmessage = (e) => {
    const event = JSON.parse(e.data);
    jobs.update(list => upsertById(list, event));
  };
  ws.onclose = () => setTimeout(connectJobsSocket, 2000); // auto-reconnect
}
```

`connectJobsSocket` is called once in `+layout.svelte`'s `onMount`.

## API client

`api.ts` exports one typed function per endpoint. No external HTTP library — plain `fetch`. Errors throw with the response body as the message. Types mirror the FastAPI Pydantic models.

```typescript
export async function search(query: string, k = 10): Promise<SearchResponse> { … }
export async function getHealth(): Promise<HealthResponse> { … }
export async function getLibrary(): Promise<LibraryResponse> { … }
export async function addFolder(path: string): Promise<RegisterFolderResponse> { … }
export async function deleteFolder(id: string): Promise<void> { … }
export async function rescanFolder(id: string): Promise<{ enqueued: number }> { … }
export async function ingest(path: string, recursive?: boolean): Promise<IngestResponse> { … }
export async function getJobs(): Promise<JobsListResponse> { … }
export async function retryJob(id: string): Promise<{ job_id: string }> { … }
export async function revealVideo(id: string): Promise<void> { … }
export async function listFs(path?: string): Promise<FsListResponse> { … }
export async function getSettings(): Promise<Record<string, unknown>> { … }
export async function patchSettings(patch: Partial<SettingsPatch>): Promise<Record<string, unknown>> { … }
```

## FastAPI changes

`app.py` gains (after all routers are registered):

```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path

_STATIC = Path(__file__).parent.parent / "static"

if _STATIC.exists():
    # html=True makes StaticFiles serve index.html for any path not found
    # in the directory — this is the SPA fallback. FastAPI routes registered
    # above are matched first (before the mount), so /api/* is unaffected.
    app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")
```

The `if _STATIC.exists()` guard means the API works normally during backend-only development before the frontend is built. No explicit catch-all route is needed: `html=True` on `StaticFiles` returns `index.html` for any path not found as a real file, which is exactly the SPA fallback behaviour.

## Build integration

`frontend/package.json` scripts:
- `dev` — Vite dev server on port 5173
- `build` — SvelteKit build → `../src/videosearch/static/`
- `test` — Vitest
- `check` — `svelte-check` + TypeScript

The `src/videosearch/static/` directory is included in the Python package via `pyproject.toml`'s `[tool.hatch.build.targets.wheel] packages` config. A note in `CONTRIBUTING.md` (or the README) documents that contributors must run `cd frontend && npm run build` before publishing a new package version.

## Testing

- **Vitest** for unit tests: `api.ts` functions (mock `fetch`, assert typed return values), store logic (`upsertById`), WebSocket reconnection logic.
- **`@testing-library/svelte`** for component tests: `MomentCard` (click emits correct event), `FolderPicker` (navigates directories, emits path on confirm), `VideoPlayer` (seeks on `activeVideo` change).
- No end-to-end tests in this phase; the backend contract is covered by `tests/api/`.
