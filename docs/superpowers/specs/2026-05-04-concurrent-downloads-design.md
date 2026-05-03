# Concurrent Model Downloads Design

**Goal:** Download all three default models simultaneously instead of serially, so users on slower connections see all progress bars moving at once. Add a per-row retry button for failed downloads.

**Non-goals:** Download throttling, max-concurrency cap, download prioritisation, progress persistence across server restarts.

---

## Architecture

Three layers of changes, each self-contained:

1. **`ModelDownloader`** — replace the queue+drain loop with a task-per-download dict. Each download is an independent `asyncio.Task` with its own progress state and lock.
2. **API** — `GET /api/models/download/progress` returns `list[DownloadProgress]` instead of a single object.
3. **`SetupModal`** — progress state becomes `DownloadProgress[]`, each model row tracks its own progress, failed rows show a retry button.

---

## Section 1: Backend — `src/videosearch/models/downloader.py`

### State

Replace the single shared progress/bytes/lock/queue with per-download dicts:

```python
self._tasks:    dict[tuple[str, str], asyncio.Task]          = {}
self._progress: dict[tuple[str, str], DownloadProgress]      = {}
self._bytes:    dict[tuple[str, str], dict[str, int]]        = {}
self._locks:    dict[tuple[str, str], threading.Lock]        = {}
```

The outer dicts are only written from the asyncio event loop (inside `_download_one` at task start), so no outer lock is needed. Per-entry locks protect the mutable bytes/progress fields that tqdm threads update.

### `start()`

Keeps its signature (called from lifespan in `app.py`) but no longer creates a queue — becomes a no-op. Kept for interface stability.

### `enqueue(model_type, model_id) -> bool`

Checks in order:
1. Unknown model → `False`
2. Already cached → `False`
3. Task exists and `not task.done()` → `False` (idempotent, prevents double-start)
4. Otherwise: `asyncio.create_task(_download_one(...))`, store in `_tasks[key]`, return `True`

The same code path handles retry — a failed task is `done()`, so a retry call creates a fresh task for that key and resets progress.

### `_download_one(model_type, model_id)`

At entry, initialises per-key state:
```python
key = (model_type, model_id)
lock = threading.Lock()
bytes_state: dict[str, int] = {"downloaded": 0, "total": 0}
self._locks[key] = lock
self._bytes[key] = bytes_state
self._progress[key] = DownloadProgress(active=True, model_type=model_type, model_id=model_id)
```

Then runs the existing HF Hub download logic unchanged. `_make_tqdm_class` takes `bytes_state` and `lock` as explicit parameters (no longer reads from `self`).

On success: sets `complete=True`, `active=False` under the entry lock.
On exception: sets `error=str(exc)`, `active=False` under the entry lock.

### `progress() -> list[DownloadProgress]`

Iterates `_progress`, acquires each entry's lock, snapshots the state, returns a list. Order is insertion order (dict in Python 3.7+).

### `_make_tqdm_class(bytes_state, lock)`

Same implementation, but receives `bytes_state` and `lock` as params instead of closing over `self._bytes` and `self._lock`.

---

## Section 2: API — `src/videosearch/api/routers/models.py`

One change — the progress endpoint signature:

```python
@router.get("/models/download/progress", response_model=list[DownloadProgress])
async def get_progress(
    downloader: ModelDownloader = Depends(get_downloader),
) -> list[DownloadProgress]:
    return downloader.progress()
```

No other routes change.

---

## Section 3: Frontend

### `frontend/src/lib/api.ts`

`getDownloadProgress()` return type changes from `Promise<DownloadProgress>` to `Promise<DownloadProgress[]>`.

### `frontend/src/lib/types.ts`

`DownloadProgress` interface is unchanged.

### `frontend/src/lib/components/SetupModal.svelte`

**State:**
```typescript
let progresses = $state<DownloadProgress[]>([]);
```
(replaces `let progress = $state<DownloadProgress | null>(null)`)

**Helpers:**
```typescript
function sectionProgress(section: ModelSection): DownloadProgress | undefined {
  return progresses.find(p => p.model_type === section.type);
}

function sectionStatus(section: ModelSection): 'cached' | 'downloading' | 'error' | 'queued' {
  if (section.entry?.cached) return 'cached';
  const p = sectionProgress(section);
  if (p?.error) return 'error';
  if (p?.active) return 'downloading';
  return 'queued';
}

function pct(section: ModelSection): number {
  const p = sectionProgress(section);
  if (!p || !p.total_bytes) return 0;
  return Math.round((p.downloaded_bytes / p.total_bytes) * 100);
}
```

**Polling:**
```typescript
pollInterval = setInterval(async () => {
  progresses = await getDownloadProgress();
  await refreshCatalog();
  if (progresses.length > 0 && progresses.every(p => !p.active)) stopPolling();
}, 1000);
```
Refreshes catalog on every tick (cheap local call, needed to pick up `cached: true` as each model finishes). Stops when all entries are inactive (complete or errored).

**Retry:**
```typescript
async function retryDownload(section: ModelSection) {
  if (section.entry) {
    await startModelDownload(section.type, section.entry.id);
    if (!pollInterval) startPolling();
  }
}
```

**Template — error branch per row:**
```svelte
{:else if status === 'error'}
  <span class="row-status error">failed</span>
  <button class="retry-btn" onclick={() => retryDownload(section)}>Retry</button>
```

Percentage display and progress bar in the template use `pct(section)` instead of `pct()`.

---

## Files changed

| File | Change |
|---|---|
| `src/videosearch/models/downloader.py` | Replace queue+drain with task dict; per-entry progress/bytes/lock |
| `tests/models/test_downloader.py` | Update existing tests; add concurrent + retry tests |
| `src/videosearch/api/routers/models.py` | Progress endpoint returns `list[DownloadProgress]` |
| `tests/api/test_models.py` | Update progress test to expect list |
| `frontend/src/lib/api.ts` | `getDownloadProgress()` returns `DownloadProgress[]` |
| `frontend/src/lib/components/SetupModal.svelte` | `progresses` state, per-section helpers, retry button |
| `frontend/src/lib/components/SetupModal.test.ts` | Update mocks and assertions for list shape; add error/retry tests |

---

## Testing

**Backend:**
- `test_concurrent_downloads_start_simultaneously` — enqueue 3 downloads with a slow fake `hf_hub_download`, assert all 3 tasks are running before any completes
- `test_progress_returns_list` — `progress()` returns a list of `DownloadProgress`
- `test_enqueue_idempotent_while_active` — calling `enqueue()` for an in-progress download returns `False`
- `test_retry_after_failure` — simulate a failed download, call `enqueue()` again, assert a new task starts and progress resets

**API:**
- `test_progress_endpoint_returns_list` — `GET /api/models/download/progress` returns a JSON array

**Frontend (Vitest):**
- Update `beforeEach` mock for `getDownloadProgress` to return `DownloadProgress[]`
- `shows downloading status for active entry` — progress list with one active entry shows that row as downloading
- `shows error status and retry button on failure` — progress entry with `error` set shows retry button
- `Retry button calls startModelDownload and restarts polling` — clicking retry calls the API and resumes polling
