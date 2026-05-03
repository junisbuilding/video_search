# Settings UX Uplift — Design

**Date:** 2026-05-03
**Status:** Approved, ready for implementation

## Goal

Replace the raw configuration form on the Settings page with a non-technical-user-friendly experience: curated model dropdowns with cached/not-cached indicators, inline download progress, a first-launch welcome modal that auto-starts default downloads, and an "Advanced options" accordion that hides port/FPS/GPU fields from everyday users.

## Target user

Non-technical. They should never see a HuggingFace repo ID, a file path, or the word "mmproj". They pick from a short named list, the app downloads, and they get on with their life.

---

## Architecture overview

Three new backend concerns:

1. **Model catalog** — a static registry of known models (Python dict), one entry per dropdown option, carrying human-readable labels, size hints, HF repo specs, and default flags.
2. **Cache detection** — `GET /api/models/catalog` enriches the catalog with live `cached: bool` per entry by inspecting the HF hub cache and `settings.models_dir`.
3. **Background download** — `POST /api/models/download` starts a sequential download queue (one at a time) as an `asyncio` task; progress is reported via in-memory state polled by `GET /api/models/download/progress`.

One new frontend concern:

4. **SetupModal** — shown on first launch (any required model not cached), auto-starts default downloads, polls progress, dismisses when all three required models are cached.

Settings page is restructured: three named model sections (stacked label → description → dropdown → inline progress), followed by an Advanced accordion (port, FPS, GPU layers, scene detection).

---

## Model catalog

Defined in `src/videosearch/models/catalog.py`. Three model types: `vision`, `siglip`, `text_embedder`.

### Vision model (VLM — captions video frames)

| id | Label | Size | vlm_model spec | vlm_mmproj spec | default |
|---|---|---|---|---|---|
| `moondream2` | moondream2 | ~2 GB | `vikhyatk/moondream2::moondream2-text-model-f16.gguf` | `vikhyatk/moondream2::mmproj-moondream2-f16.gguf` | ✓ |
| `llava-1.5-7b` | LLaVA 1.5 · 7B | ~4 GB | `mys/ggml_llava-v1.5-7b::ggml-model-q4_k.gguf` | `mys/ggml_llava-v1.5-7b::mmproj-model-f16.gguf` | |
| `llava-1.5-13b` | LLaVA 1.5 · 13B | ~8 GB | `mys/ggml_llava-v1.5-13b::ggml-model-q4_k.gguf` | `mys/ggml_llava-v1.5-13b::mmproj-model-f16.gguf` | |

> **Note for implementer:** verify exact filenames against the HF repo at implementation time. The `::` separator is the existing `resolve_gguf` convention. All GGUF files are cached to `settings.models_dir`.

### Image understanding model (SigLIP — embeds video frames)

| id | Label | Size | hf_repo | default |
|---|---|---|---|---|
| `siglip2-base` | SigLIP Base | ~1.2 GB | `google/siglip2-base-patch16-256` | ✓ |
| `siglip2-large` | SigLIP Large | ~3.5 GB | `google/siglip2-large-patch16-256` | |
| `siglip-so400m` | SigLIP SO400M | ~1.6 GB | `google/siglip-so400m-patch14-384` | |

### Search model (BGE text embedder)

| id | Label | Size | hf_repo | default |
|---|---|---|---|---|
| `bge-small-en` | BGE Small (English) | ~130 MB | `BAAI/bge-small-en-v1.5` | ✓ |
| `bge-base-en` | BGE Base (English) | ~430 MB | `BAAI/bge-base-en-v1.5` | |
| `bge-large-en` | BGE Large (English) | ~1.3 GB | `BAAI/bge-large-en-v1.5` | |
| `bge-m3` | BGE M3 (multilingual) | ~2 GB | `BAAI/bge-m3` | |

---

## Backend

### New file: `src/videosearch/models/catalog.py`

Defines a `ModelEntry` dataclass and `CATALOG` dict:

```python
@dataclass
class ModelEntry:
    id: str
    label: str
    size_label: str           # e.g. "~2 GB"
    hf_repo: str | None       # HF transformer repo ID (siglip, text_embedder); None for vision
    vlm_model: str | None     # repo_id::filename for GGUF (vision only)
    vlm_mmproj: str | None    # repo_id::filename for mmproj (vision only)
    default: bool

CATALOG: dict[str, list[ModelEntry]] = {
    "vision": [...],
    "siglip": [...],
    "text_embedder": [...],
}
```

Exposes two helpers:
- `get_default(model_type: str) -> ModelEntry` — returns the entry with `default=True`
- `find_by_id(model_type: str, model_id: str) -> ModelEntry | None`

### New file: `src/videosearch/models/downloader.py`

Owns the background download queue and progress state.

```python
@dataclass
class DownloadProgress:
    active: bool = False
    model_type: str = ""
    model_id: str = ""
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error: str | None = None
    complete: bool = False

class ModelDownloader:
    """Runs one download at a time in an asyncio executor. Thread-safe progress."""
    def __init__(self, models_dir: Path): ...
    async def enqueue(self, model_type: str, model_id: str) -> None: ...
    def progress(self) -> DownloadProgress: ...
```

`enqueue` appends to an internal queue. A single background `asyncio.Task` drains it sequentially. Each GGUF file is downloaded via `hf_hub_download(..., tqdm_class=_ProgressTqdm)` where `_ProgressTqdm` is a minimal `tqdm` subclass that writes `(n, total)` into a shared `threading.Lock`-protected state. HF transformer models (SigLIP, BGE) are downloaded by calling `snapshot_download(repo_id)` in an executor — no model loading, just caching.

Cache detection uses `try_to_load_from_cache`:
- GGUF: `try_to_load_from_cache(repo_id, filename, cache_dir=models_dir)` → not `None` means cached.
- HF transformer: `try_to_load_from_cache(repo_id, "config.json")` → not `None` means cached.

`ModelDownloader` is instantiated in `app.py` lifespan (before the model conditional) and stored on `app.state.downloader`.

### Modified: `src/videosearch/api/app.py`

In `lifespan`, before the `if settings.vlm_model and settings.vlm_mmproj:` block:

```python
from videosearch.models.downloader import ModelDownloader
downloader = ModelDownloader(settings.models_dir)
app.state.downloader = downloader
```

### New router: `src/videosearch/api/routers/models.py`

```
GET  /api/models/catalog          → CatalogResponse
POST /api/models/download         → {"queued": true}
GET  /api/models/download/progress → DownloadProgress
```

**`GET /api/models/catalog`** — returns the full catalog enriched with `cached: bool` per entry, `first_run: bool` (true when no required model is cached in any slot), and `active_models` (which catalog IDs are currently loaded in this server process — populated from `app.state` if models are loaded, otherwise empty strings).

Response shape:
```json
{
  "first_run": true,
  "active_models": {"vision": "moondream2", "siglip": "siglip2-base", "text_embedder": "bge-small-en"},
  "vision":        [{"id": "moondream2", "label": "moondream2", "size_label": "~2 GB", "cached": false, "default": true}, ...],
  "siglip":        [...],
  "text_embedder": [...]
}
```

`active_models` values are empty strings when the server started without models loaded. The Settings page uses `active_models` to show "⚠ requires restart" when the saved selection differs from what is currently running.

**`POST /api/models/download`** body: `{"model_type": "vision", "model_id": "moondream2"}`. Calls `downloader.enqueue(...)`. If the model is already cached, returns `{"queued": false, "reason": "already_cached"}`.

**`GET /api/models/download/progress`** — returns the current `DownloadProgress` as JSON.

### `src/videosearch/api/routers/settings.py` — no changes

The PATCH endpoint continues to accept raw `vlm_model` / `vlm_mmproj` strings (the `repo_id::filename` format). The frontend resolves the user's dropdown selection to these raw strings via the catalog before calling PATCH — it does not send catalog IDs.

### Modified: `src/videosearch/api/deps.py`

```python
def get_downloader(conn: HTTPConnection) -> ModelDownloader:
    return conn.app.state.downloader
```

---

## Frontend

### New file: `frontend/src/lib/api.ts` additions

```typescript
export async function getModelCatalog(): Promise<ModelCatalogResponse> { … }
export async function startModelDownload(model_type: string, model_id: string): Promise<void> { … }
export async function getDownloadProgress(): Promise<DownloadProgress> { … }
```

### New component: `frontend/src/lib/components/SetupModal.svelte`

Shown on the very first launch when `catalog.first_run === true` and `localStorage.getItem('setup_seen')` is not set. On dismiss (auto or manual), sets `localStorage.setItem('setup_seen', '1')` — the modal never re-appears even if models are later deleted. The amber nav dot handles the ongoing "models missing" state for returning users; the modal is a one-time onboarding experience only.

Behaviour:
- On mount: calls `getModelCatalog()`, then immediately calls `startModelDownload` for each default model that is not yet cached (sequentially: vision → siglip → text_embedder, but enqueueing all three immediately since the server queues them).
- Polls `getDownloadProgress()` every 1 s while `active === true`.
- Re-fetches catalog after each poll completes a model (to update `cached` flags).
- "Customise ↗" link navigates to `/settings` without dismissing the modal (download continues).
- Auto-dismisses when `catalog.first_run === false` (all required models cached).

### Modified: `frontend/src/routes/+layout.svelte`

- On mount: fetches `getModelCatalog()`. If `first_run`, renders `<SetupModal />`.
- Stores `setupNeeded = $state(false)` which is also `true` if catalog shows any required model uncached (even after initial setup — e.g. user deleted cache).
- Passes `setupNeeded` as prop to the navbar to render the amber dot on the Settings link.

### Modified: `frontend/src/routes/settings/+page.svelte`

Complete redesign. Structure:

```
Settings
  ├── Vision model section
  │     label: "Vision model"
  │     description: "Describes what's happening in each frame of your videos — the smarter the model, the better your search results."
  │     <select> with catalog options (label + size)
  │     cached indicator OR inline progress bar
  │
  ├── Image understanding section
  │     label: "Image understanding"
  │     description: "Recognises objects, scenes, and people in video frames so you can search visually."
  │     <select> + cached / progress
  │
  ├── Search model section
  │     label: "Search model"
  │     description: "Understands your search phrases and matches them to moments in your videos."
  │     <select> + cached / progress
  │
  └── Advanced options <details> accordion
        FPS · Scene detection · Port (⚠ restart) · GPU layers
        Save button (only for Advanced fields)
```

**Model selection behaviour:**
- Changing a dropdown auto-saves the selection to `PATCH /api/settings` immediately (no Save button needed for model changes). The frontend resolves the selected catalog entry to raw strings before calling PATCH: for vision entries, sends `vlm_model` and `vlm_mmproj`; for siglip/text_embedder entries, sends `siglip_model` or `text_embedder`.
- If the selected model is not cached, `POST /api/models/download` is called immediately after saving.
- If the selected model's catalog ID differs from `catalog.active_models[type]`, show a muted "⚠ requires restart" hint beneath the dropdown.

**Cached indicator:** `● Cached` in green. **Not cached:** `○ ~X GB` in muted grey + a small "Download" button that calls `startModelDownload`.

**Inline progress:** appears below the dropdown when `downloadProgress.model_type` matches this section's type and `downloadProgress.active === true`.

---

## Testing

**`src/videosearch/models/catalog.py`**
- `test_catalog_has_defaults` — each model type has exactly one `default=True` entry.
- `test_find_by_id_returns_none_for_unknown` — `find_by_id("vision", "bogus")` returns `None`.

**`src/videosearch/api/routers/models.py`**
- `test_catalog_endpoint_shape` — GET returns keys `first_run`, `vision`, `siglip`, `text_embedder`.
- `test_download_already_cached` — POST for a cached model returns `queued: false`.
- `test_download_enqueues_unknown_model_returns_404` — POST for unknown model_id returns 404.

**`src/videosearch/models/downloader.py`**
- `test_progress_initial_state` — fresh downloader reports `active=False`.
- `test_enqueue_already_cached_skips` — enqueuing cached model does not set `active=True`.

**Frontend (Vitest + @testing-library/svelte)**
- `SetupModal`: mounts when `first_run=true`, calls `startModelDownload` for each default on mount, dismisses when catalog switches to `first_run=false`.
- Settings page: changing a `<select>` calls `patchSettings` and `startModelDownload` for uncached model.
