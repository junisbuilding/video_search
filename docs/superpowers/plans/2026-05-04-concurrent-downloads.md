# Concurrent Model Downloads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Download all three default models simultaneously and add a per-row retry button for failed downloads.

**Architecture:** Replace `ModelDownloader`'s serial queue+drain loop with a task-per-download dict — `enqueue()` fires `asyncio.create_task` immediately and tracks each download in per-key progress/bytes/lock dicts. The progress API returns `list[DownloadProgress]`. SetupModal tracks `progresses: DownloadProgress[]` and renders per-section status including an error/retry state.

**Tech Stack:** Python asyncio, huggingface_hub, FastAPI, Svelte 5, Vitest.

---

> **Running Python tests in a worktree:** `uv run pytest` will fail (llama-cpp-python build). Use the main project venv:
> ```bash
> PYTHONPATH=$(pwd)/src /mnt/c/Users/jun/code/video_search/.venv/bin/pytest <test_path> -v --rootdir=/mnt/c/Users/jun/code/video_search
> ```

---

## File map

- Modify: `src/videosearch/models/downloader.py` — replace queue+drain with task dict; per-entry progress/bytes/lock
- Modify: `tests/models/test_downloader.py` — update broken tests; add concurrent + retry tests
- Modify: `src/videosearch/api/routers/models.py` — progress endpoint returns `list[DownloadProgress]`
- Modify: `tests/api/conftest.py` — `mock_downloader.progress.return_value` becomes `[]`
- Modify: `tests/api/test_models.py` — update progress test to expect list
- Modify: `frontend/src/lib/api.ts` — `getDownloadProgress()` returns `DownloadProgress[]`
- Modify: `frontend/src/lib/components/SetupModal.svelte` — `progresses` state, per-section helpers, retry button
- Modify: `frontend/src/lib/components/SetupModal.test.ts` — update mocks; add error + retry tests

---

### Task 1: Refactor ModelDownloader to concurrent tasks

**Files:**
- Modify: `src/videosearch/models/downloader.py`
- Modify: `tests/models/test_downloader.py`

- [ ] **Step 1: Update the two tests that will break**

In `tests/models/test_downloader.py`, replace `test_progress_initial_state` and the last assertion of `test_enqueue_already_cached_skips`:

```python
# Replace test_progress_initial_state with:
def test_progress_returns_empty_list_initially(downloader):
    assert downloader.progress() == []


# In test_enqueue_already_cached_skips, replace the last line:
# OLD: assert downloader.progress().active is False
# NEW:
@pytest.mark.anyio
async def test_enqueue_already_cached_skips(downloader):
    await downloader.start()
    with patch("videosearch.models.downloader.try_to_load_from_cache", return_value="/cached/config.json"):
        queued = await downloader.enqueue("siglip", "siglip2-base")
    assert queued is False
    assert downloader.progress() == []
```

- [ ] **Step 2: Add new failing tests at the end of `tests/models/test_downloader.py`**

```python
@pytest.mark.anyio
async def test_concurrent_downloads_create_separate_tasks(tmp_path, monkeypatch):
    """enqueue() fires an independent task per model — no serial blocking."""
    def fake_hf_hub_download(*args, **kwargs):
        return str(tmp_path / "fake.gguf")

    def fake_snapshot_download(*args, **kwargs):
        return str(tmp_path / "fake_snapshot")

    monkeypatch.setattr("videosearch.models.downloader.hf_hub_download", fake_hf_hub_download)
    monkeypatch.setattr("videosearch.models.downloader.snapshot_download", fake_snapshot_download)

    downloader = ModelDownloader(tmp_path)
    await downloader.start()

    await downloader.enqueue("vision", "moondream2")
    await downloader.enqueue("siglip", "siglip2-base")
    await downloader.enqueue("text_embedder", "bge-small-en")

    assert len(downloader._tasks) == 3
    assert ("vision", "moondream2") in downloader._tasks
    assert ("siglip", "siglip2-base") in downloader._tasks
    assert ("text_embedder", "bge-small-en") in downloader._tasks


@pytest.mark.anyio
async def test_enqueue_returns_false_while_active(tmp_path, monkeypatch):
    """Calling enqueue() for an already-running download is a no-op."""
    monkeypatch.setattr(
        "videosearch.models.downloader.hf_hub_download",
        lambda *a, **kw: str(tmp_path / "fake.gguf"),
    )

    downloader = ModelDownloader(tmp_path)
    await downloader.start()

    result1 = await downloader.enqueue("vision", "moondream2")
    assert result1 is True

    # Task created but not yet done (no await between enqueue calls)
    result2 = await downloader.enqueue("vision", "moondream2")
    assert result2 is False


@pytest.mark.anyio
async def test_retry_after_failure(tmp_path, monkeypatch):
    """After a failed download, enqueue() starts a fresh task and resets progress."""
    call_count = 0

    def fail_then_succeed(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("network error")
        return str(tmp_path / "fake.gguf")

    monkeypatch.setattr("videosearch.models.downloader.hf_hub_download", fail_then_succeed)

    downloader = ModelDownloader(tmp_path)
    await downloader.start()

    await downloader.enqueue("vision", "moondream2")
    await downloader._tasks[("vision", "moondream2")]  # wait for failure

    failed = downloader.progress()
    assert any(p.error is not None for p in failed)
    assert all(not p.active for p in failed)

    # Retry — task.done() is True, so enqueue() accepts it
    result = await downloader.enqueue("vision", "moondream2")
    assert result is True

    await downloader._tasks[("vision", "moondream2")]  # wait for retry

    retried = downloader.progress()
    assert all(p.error is None for p in retried)
    assert any(p.complete for p in retried)


@pytest.mark.anyio
async def test_progress_returns_list_with_entries(tmp_path, monkeypatch):
    """progress() returns a list with one entry per started download."""
    monkeypatch.setattr(
        "videosearch.models.downloader.hf_hub_download",
        lambda *a, **kw: str(tmp_path / "fake.gguf"),
    )
    monkeypatch.setattr(
        "videosearch.models.downloader.snapshot_download",
        lambda *a, **kw: str(tmp_path / "snap"),
    )

    downloader = ModelDownloader(tmp_path)
    await downloader.start()

    await downloader.enqueue("siglip", "siglip2-base")
    await downloader._tasks[("siglip", "siglip2-base")]

    result = downloader.progress()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].model_type == "siglip"
    assert result[0].complete is True
```

- [ ] **Step 3: Run new tests to verify they fail**

```bash
PYTHONPATH=$(pwd)/src /mnt/c/Users/jun/code/video_search/.venv/bin/pytest tests/models/test_downloader.py -v --rootdir=/mnt/c/Users/jun/code/video_search 2>&1 | tail -20
```

Expected: new tests FAIL (methods don't exist yet), updated tests also FAIL.

- [ ] **Step 4: Replace `src/videosearch/models/downloader.py`**

```python
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from pathlib import Path

import tqdm as tqdm_lib
from huggingface_hub import hf_hub_download, snapshot_download, try_to_load_from_cache

from videosearch.models.catalog import ModelEntry, find_by_id


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
    """Downloads models concurrently — one asyncio task per model. Thread-safe progress."""

    def __init__(self, models_dir: Path, token: str | None = None) -> None:
        self._models_dir = models_dir
        self._token = token
        self._tasks: dict[tuple[str, str], asyncio.Task] = {}
        self._progress: dict[tuple[str, str], DownloadProgress] = {}
        self._bytes: dict[tuple[str, str], dict[str, int]] = {}
        self._locks: dict[tuple[str, str], threading.Lock] = {}

    async def start(self) -> None:
        """No-op — kept for interface compatibility with lifespan caller."""

    def is_cached(self, model_type: str, model_id: str) -> bool:
        entry = find_by_id(model_type, model_id)
        if entry is None:
            return False
        if model_type == "vision":
            return self._vision_cached(entry)
        assert entry.hf_repo is not None
        result = try_to_load_from_cache(entry.hf_repo, "config.json")
        return result is not None

    def _vision_cached(self, entry: ModelEntry) -> bool:
        assert entry.vlm_model and entry.vlm_mmproj
        repo1, file1 = entry.vlm_model.split("::", 1)
        repo2, file2 = entry.vlm_mmproj.split("::", 1)
        m = try_to_load_from_cache(repo1, file1, cache_dir=str(self._models_dir))
        p = try_to_load_from_cache(repo2, file2, cache_dir=str(self._models_dir))
        return m is not None and p is not None

    async def enqueue(self, model_type: str, model_id: str) -> bool:
        """Start a download task. Returns False if unknown, cached, or already running."""
        if find_by_id(model_type, model_id) is None:
            return False
        if self.is_cached(model_type, model_id):
            return False
        key = (model_type, model_id)
        task = self._tasks.get(key)
        if task is not None and not task.done():
            return False
        self._tasks[key] = asyncio.create_task(self._download_one(model_type, model_id))
        return True

    def progress(self) -> list[DownloadProgress]:
        result = []
        for key, dp in self._progress.items():
            lock = self._locks[key]
            bytes_state = self._bytes[key]
            with lock:
                result.append(DownloadProgress(
                    active=dp.active,
                    model_type=dp.model_type,
                    model_id=dp.model_id,
                    downloaded_bytes=bytes_state["downloaded"],
                    total_bytes=bytes_state["total"],
                    error=dp.error,
                    complete=dp.complete,
                ))
        return result

    async def _download_one(self, model_type: str, model_id: str) -> None:
        key = (model_type, model_id)
        lock = threading.Lock()
        bytes_state: dict[str, int] = {"downloaded": 0, "total": 0}
        self._locks[key] = lock
        self._bytes[key] = bytes_state
        self._progress[key] = DownloadProgress(
            active=True, model_type=model_type, model_id=model_id
        )

        entry = find_by_id(model_type, model_id)
        assert entry is not None

        try:
            loop = asyncio.get_running_loop()
            tqdm_cls = self._make_tqdm_class(bytes_state, lock)

            if model_type == "vision":
                assert entry.vlm_model and entry.vlm_mmproj
                repo1, file1 = entry.vlm_model.split("::", 1)
                repo2, file2 = entry.vlm_mmproj.split("::", 1)
                await loop.run_in_executor(
                    None,
                    lambda: hf_hub_download(
                        repo1, file1,
                        cache_dir=str(self._models_dir),
                        tqdm_class=tqdm_cls,
                        token=self._token,
                    ),
                )
                await loop.run_in_executor(
                    None,
                    lambda: hf_hub_download(
                        repo2, file2,
                        cache_dir=str(self._models_dir),
                        tqdm_class=tqdm_cls,
                        token=self._token,
                    ),
                )
            else:
                assert entry.hf_repo is not None
                await loop.run_in_executor(
                    None,
                    lambda: snapshot_download(
                        entry.hf_repo,
                        tqdm_class=tqdm_cls,
                        token=self._token,
                    ),
                )

            with lock:
                self._progress[key].active = False
                self._progress[key].complete = True

        except Exception as exc:
            with lock:
                self._progress[key].active = False
                self._progress[key].error = str(exc)

    def _make_tqdm_class(self, bytes_state: dict[str, int], lock: threading.Lock):
        class _ProgressTqdm(tqdm_lib.tqdm):
            def update(self, n=1):
                super().update(n)
                with lock:
                    bytes_state["downloaded"] = int(self.n)
                    bytes_state["total"] = int(self.total or 0)

        return _ProgressTqdm
```

- [ ] **Step 5: Run all downloader tests**

```bash
PYTHONPATH=$(pwd)/src /mnt/c/Users/jun/code/video_search/.venv/bin/pytest tests/models/test_downloader.py -v --rootdir=/mnt/c/Users/jun/code/video_search 2>&1 | tail -20
```

Expected: all tests pass (the old 9 tests now pass with updated assertions, plus 4 new tests pass).

- [ ] **Step 6: Commit**

```bash
git add src/videosearch/models/downloader.py tests/models/test_downloader.py
git commit -m "feat: replace serial download queue with concurrent asyncio tasks"
```

---

### Task 2: Update progress API endpoint

**Files:**
- Modify: `tests/api/conftest.py`
- Modify: `tests/api/test_models.py`
- Modify: `src/videosearch/api/routers/models.py`

- [ ] **Step 1: Update `tests/api/conftest.py` — mock returns list**

In `tests/api/conftest.py`, find the `mock_downloader` fixture. Change line:

```python
# OLD:
m.progress.return_value = DownloadProgress()
# NEW:
m.progress.return_value = []
```

The fixture should look like:

```python
@pytest.fixture
def mock_downloader():
    m = MagicMock()
    m.is_cached.return_value = False
    m.enqueue = AsyncMock(return_value=True)
    m.progress.return_value = []
    return m
```

- [ ] **Step 2: Update `test_download_progress_returns_progress` in `tests/api/test_models.py`**

Replace the existing test with:

```python
def test_download_progress_returns_list(client, mock_downloader):
    mock_downloader.progress.return_value = [
        DownloadProgress(
            active=True, model_type="siglip", model_id="siglip2-base",
            downloaded_bytes=100, total_bytes=1000,
        )
    ]
    r = client.get("/api/models/download/progress")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["active"] is True
    assert data[0]["downloaded_bytes"] == 100
    assert data[0]["total_bytes"] == 1000
```

- [ ] **Step 3: Run to verify the test fails**

```bash
PYTHONPATH=$(pwd)/src /mnt/c/Users/jun/code/video_search/.venv/bin/pytest tests/api/test_models.py::test_download_progress_returns_list -v --rootdir=/mnt/c/Users/jun/code/video_search
```

Expected: FAIL — response is an object, not a list.

- [ ] **Step 4: Update the progress endpoint in `src/videosearch/api/routers/models.py`**

Find `get_progress` and replace it:

```python
@router.get("/models/download/progress", response_model=list[DownloadProgress])
async def get_progress(
    downloader: ModelDownloader = Depends(get_downloader),
) -> list[DownloadProgress]:
    return downloader.progress()
```

- [ ] **Step 5: Run all models API tests**

```bash
PYTHONPATH=$(pwd)/src /mnt/c/Users/jun/code/video_search/.venv/bin/pytest tests/api/test_models.py -v --rootdir=/mnt/c/Users/jun/code/video_search
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/videosearch/api/routers/models.py tests/api/conftest.py tests/api/test_models.py
git commit -m "feat: progress endpoint returns list[DownloadProgress] for concurrent tracking"
```

---

### Task 3: Update frontend — api.ts, SetupModal, tests

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/components/SetupModal.svelte`
- Modify: `frontend/src/lib/components/SetupModal.test.ts`

- [ ] **Step 1: Update `getDownloadProgress` return type in `frontend/src/lib/api.ts`**

Find the `getDownloadProgress` function and change its return type:

```typescript
// OLD:
export async function getDownloadProgress(): Promise<DownloadProgress> {
  return apiFetch('/api/models/download/progress');
}

// NEW:
export async function getDownloadProgress(): Promise<DownloadProgress[]> {
  return apiFetch('/api/models/download/progress');
}
```

- [ ] **Step 2: Update frontend tests to match new API shape**

In `frontend/src/lib/components/SetupModal.test.ts`, make these changes:

1. In `beforeEach`, change the `getDownloadProgress` mock from a single object to an empty array:

```typescript
// OLD:
vi.mocked(api.getDownloadProgress).mockResolvedValue(idleProgress);
// NEW:
vi.mocked(api.getDownloadProgress).mockResolvedValue([]);
```

2. In the `sets localStorage setup_seen` test, change the progress mock to a list:

```typescript
// OLD:
vi.mocked(api.getDownloadProgress).mockResolvedValue({ ...idleProgress, complete: true });
// NEW:
vi.mocked(api.getDownloadProgress).mockResolvedValue([{ ...idleProgress, complete: true }]);
```

3. Add two new tests at the end of the `describe` block:

```typescript
it('shows error status and retry button for a failed download', async () => {
  vi.mocked(api.getDownloadProgress).mockResolvedValue([
    {
      active: false, model_type: 'siglip', model_id: 'siglip2-base',
      downloaded_bytes: 0, total_bytes: 0, error: 'network error', complete: false,
    },
  ]);
  render(SetupModal);
  await waitFor(() => {
    expect(screen.getByText('failed')).toBeInTheDocument();
    expect(screen.getByText('Retry')).toBeInTheDocument();
  }, { timeout: 3000 });
});

it('Retry button calls startModelDownload with the failed model', async () => {
  vi.mocked(api.getDownloadProgress).mockResolvedValue([
    {
      active: false, model_type: 'siglip', model_id: 'siglip2-base',
      downloaded_bytes: 0, total_bytes: 0, error: 'network error', complete: false,
    },
  ]);
  render(SetupModal);
  await waitFor(() => screen.getByText('Retry'), { timeout: 3000 });
  fireEvent.click(screen.getByText('Retry'));
  await waitFor(() => {
    // 3 calls from beginDownloads + 1 from retry = 4 total
    expect(api.startModelDownload).toHaveBeenCalledTimes(4);
    expect(api.startModelDownload).toHaveBeenLastCalledWith('siglip', 'siglip2-base');
  });
});
```

- [ ] **Step 3: Run tests to verify new tests fail and existing tests fail due to type change**

```bash
cd frontend && npm test -- --run 2>&1 | tail -20
```

Expected: TypeScript errors or test failures because SetupModal still uses single `progress` state.

- [ ] **Step 4: Replace `frontend/src/lib/components/SetupModal.svelte`**

```svelte
<!-- frontend/src/lib/components/SetupModal.svelte -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { getModelCatalog, startModelDownload, getDownloadProgress, getSettings, patchSettings } from '$lib/api';
  import type { ModelCatalogEntry, DownloadProgress } from '$lib/types';

  let visible = $state(true);
  let step = $state<'token' | 'downloading'>('token');
  let tokenInput = $state('');
  let visionEntries = $state<ModelCatalogEntry[]>([]);
  let siglipEntries = $state<ModelCatalogEntry[]>([]);
  let textEntries = $state<ModelCatalogEntry[]>([]);
  let progresses = $state<DownloadProgress[]>([]);
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  type ModelSection = { type: string; label: string; entry: ModelCatalogEntry | undefined };

  let sections = $derived.by<ModelSection[]>(() => [
    { type: 'vision',        label: 'Vision model',        entry: visionEntries.find(e => e.default) },
    { type: 'siglip',       label: 'Image understanding',  entry: siglipEntries.find(e => e.default) },
    { type: 'text_embedder', label: 'Search model',        entry: textEntries.find(e => e.default) },
  ]);

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

  async function refreshCatalog() {
    const catalog = await getModelCatalog();
    visionEntries = catalog.vision;
    siglipEntries = catalog.siglip;
    textEntries = catalog.text_embedder;
    if (!catalog.first_run) {
      localStorage.setItem('setup_seen', '1');
      stopPolling();
      visible = false;
    }
  }

  function startPolling() {
    pollInterval = setInterval(async () => {
      progresses = await getDownloadProgress();
      await refreshCatalog();
      if (progresses.length > 0 && progresses.every(p => !p.active)) stopPolling();
    }, 1000);
  }

  function stopPolling() {
    if (pollInterval !== null) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  async function beginDownloads() {
    step = 'downloading';
    for (const [type, entries] of [
      ['vision', visionEntries] as const,
      ['siglip', siglipEntries] as const,
      ['text_embedder', textEntries] as const,
    ]) {
      const def = entries.find(e => e.default);
      if (def && !def.cached) {
        await startModelDownload(type, def.id);
      }
    }
    startPolling();
  }

  async function handleContinue() {
    if (tokenInput.trim()) {
      await patchSettings({ hf_token: tokenInput.trim() });
    }
    await beginDownloads();
  }

  async function handleSkip() {
    await beginDownloads();
  }

  async function retryDownload(section: ModelSection) {
    if (section.entry) {
      await startModelDownload(section.type, section.entry.id);
      if (!pollInterval) startPolling();
    }
  }

  onMount(async () => {
    const [catalog, settings] = await Promise.all([getModelCatalog(), getSettings()]);
    visionEntries = catalog.vision;
    siglipEntries = catalog.siglip;
    textEntries = catalog.text_embedder;

    if (settings.hf_token !== null) {
      await beginDownloads();
    }
  });

  onDestroy(stopPolling);

  function customise() {
    goto('/settings');
  }
</script>

{#if visible}
  <div class="overlay" role="dialog" aria-modal="true" aria-label="First time setup">
    <div class="modal">
      <div class="modal-head">
        <div class="logo-dot" aria-hidden="true"></div>
        <h2 class="modal-title">Welcome to Videosearch</h2>
      </div>

      {#if step === 'token'}
        <p class="modal-sub">A Hugging Face token speeds up AI model downloads.</p>
        <div class="token-section">
          <input
            type="password"
            class="token-input"
            placeholder="hf_..."
            bind:value={tokenInput}
          />
          <p class="token-hint">Free at huggingface.co · optional but recommended</p>
        </div>
        <div class="token-actions">
          <button class="skip-btn" type="button" onclick={handleSkip}>Skip</button>
          <button class="continue-btn" type="button" onclick={handleContinue}>Continue</button>
        </div>
      {:else}
        <p class="modal-sub">Downloading AI models — this only happens once.</p>
        <div class="model-rows">
          {#each sections as section}
            {@const status = sectionStatus(section)}
            <div class="model-row">
              <div class="row-header">
                <span class="row-label">{section.label}</span>
                <span class="row-meta">{section.entry?.label} · {section.entry?.size_label}</span>
                {#if status === 'cached'}
                  <span class="row-status cached">✓</span>
                {:else if status === 'downloading'}
                  <span class="row-status downloading">{pct(section)}%</span>
                {:else if status === 'error'}
                  <span class="row-status error">failed</span>
                  <button class="retry-btn" type="button" onclick={() => retryDownload(section)}>Retry</button>
                {:else}
                  <span class="row-status queued">queued</span>
                {/if}
              </div>
              <div class="bar-track">
                {#if status === 'downloading'}
                  <div class="bar-fill" style="width: {pct(section)}%"></div>
                {:else if status === 'cached'}
                  <div class="bar-fill full"></div>
                {:else}
                  <div class="bar-empty"></div>
                {/if}
              </div>
            </div>
          {/each}
        </div>
        <div class="modal-footer">
          <span class="footer-hint">You can change models any time in Settings</span>
          <button class="customise-btn" onclick={customise}>Customise ↗</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }
  .modal {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
    padding: 24px;
    width: 380px;
    max-width: 90vw;
  }
  .modal-head {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
  }
  .logo-dot {
    width: 14px;
    height: 14px;
    background: #4ade80;
    border-radius: 3px;
    flex-shrink: 0;
  }
  .modal-title {
    font-size: 14px;
    font-weight: 700;
    color: #e0e0e0;
  }
  .modal-sub {
    font-size: 10px;
    color: #555;
    margin-bottom: 16px;
    padding-left: 24px;
  }
  .token-section {
    margin-bottom: 16px;
  }
  .token-input {
    width: 100%;
    background: #111;
    border: 1px solid #333;
    border-radius: 6px;
    color: #e0e0e0;
    font-size: 11px;
    padding: 8px 10px;
    box-sizing: border-box;
    margin-bottom: 6px;
  }
  .token-input::placeholder { color: #444; }
  .token-hint {
    font-size: 9px;
    color: #444;
    margin: 0;
  }
  .token-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-bottom: 4px;
  }
  .skip-btn {
    background: none;
    border: 1px solid #333;
    border-radius: 4px;
    font-size: 10px;
    color: #666;
    cursor: pointer;
    padding: 4px 10px;
  }
  .continue-btn {
    background: #4ade80;
    border: none;
    border-radius: 4px;
    font-size: 10px;
    color: #000;
    font-weight: 600;
    cursor: pointer;
    padding: 4px 12px;
  }
  .model-rows {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-bottom: 20px;
  }
  .row-header {
    display: flex;
    align-items: baseline;
    gap: 6px;
    margin-bottom: 5px;
  }
  .row-label {
    font-size: 10px;
    font-weight: 600;
    color: #e0e0e0;
  }
  .row-meta {
    font-size: 9px;
    color: #555;
    flex: 1;
  }
  .row-status { font-size: 9px; }
  .row-status.cached { color: #4ade80; }
  .row-status.downloading { color: #4ade80; }
  .row-status.queued { color: #555; }
  .row-status.error { color: #f87171; }
  .retry-btn {
    background: none;
    border: 1px solid #444;
    border-radius: 3px;
    font-size: 9px;
    color: #f87171;
    cursor: pointer;
    padding: 2px 6px;
  }
  .bar-track {
    background: #2a2a2a;
    border-radius: 2px;
    height: 3px;
    overflow: hidden;
  }
  .bar-fill {
    background: #4ade80;
    height: 3px;
    border-radius: 2px;
    transition: width 0.4s ease;
  }
  .bar-fill.full { width: 100%; }
  .bar-empty { height: 3px; }
  .modal-footer {
    border-top: 1px solid #2a2a2a;
    padding-top: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .footer-hint {
    font-size: 9px;
    color: #444;
  }
  .customise-btn {
    background: none;
    border: none;
    font-size: 9px;
    color: #4ade80;
    cursor: pointer;
    padding: 0;
  }
</style>
```

- [ ] **Step 5: Run all frontend tests**

```bash
cd frontend && npm test -- --run 2>&1 | tail -20
```

Expected: 82 tests passed across 13 files (80 existing + 2 new).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/components/SetupModal.svelte frontend/src/lib/components/SetupModal.test.ts
git commit -m "feat: concurrent progress tracking and retry button in SetupModal"
```

---

### Task 4: Build frontend and run full test suite

**Files:**
- Modify: `src/videosearch/static/` (built output)

- [ ] **Step 1: Build frontend**

```bash
cd frontend && npm run build
```

Expected: `Wrote site to "../src/videosearch/static"` with no errors.

- [ ] **Step 2: Run all Python tests**

```bash
PYTHONPATH=$(pwd)/src /mnt/c/Users/jun/code/video_search/.venv/bin/pytest tests/ -q --rootdir=/mnt/c/Users/jun/code/video_search
```

Expected: 191+ passed (187 existing + 4 new downloader tests). No failures.

- [ ] **Step 3: Run all frontend tests**

```bash
cd frontend && npm test -- --run
```

Expected: 82 passed.

- [ ] **Step 4: Commit static bundle**

```bash
git add src/videosearch/static/
git commit -m "build: update static bundle with concurrent download UI"
```
