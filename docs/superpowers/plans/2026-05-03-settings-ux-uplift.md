# Settings UX Uplift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace free-text model config fields with curated dropdowns, inline download progress, a first-launch onboarding modal, and an Advanced accordion hiding technical options.

**Architecture:** New `catalog.py` defines known models; new `downloader.py` manages a background asyncio download queue with tqdm-based progress tracking; three new `/api/models/*` endpoints expose catalog+progress to the frontend; the Settings page is redesigned with stacked labels and auto-save-on-select; `SetupModal.svelte` appears on first launch and auto-starts default downloads.

**Tech Stack:** Python (FastAPI, huggingface_hub, tqdm), SvelteKit 2 / Svelte 5 runes, `@testing-library/svelte`, Vitest, pytest

---

## File map

**New Python:**
- `src/videosearch/models/catalog.py` — ModelEntry dataclass + CATALOG + helpers
- `src/videosearch/models/downloader.py` — DownloadProgress + ModelDownloader
- `src/videosearch/api/routers/models.py` — `/api/models/catalog`, `/api/models/download`, `/api/models/download/progress`
- `tests/models/test_catalog.py`
- `tests/models/test_downloader.py`
- `tests/api/test_models.py`

**Modified Python:**
- `src/videosearch/api/app.py` — instantiate ModelDownloader, register models router
- `src/videosearch/api/deps.py` — add `get_downloader`
- `tests/api/conftest.py` — add `mock_downloader` fixture

**New Frontend:**
- `frontend/src/lib/components/SetupModal.svelte`
- `frontend/src/lib/components/SetupModal.test.ts`

**Modified Frontend:**
- `frontend/src/lib/types.ts` — add `ModelEntry`, `ModelCatalogResponse`, `DownloadProgress`
- `frontend/src/lib/api.ts` — add `getModelCatalog`, `startModelDownload`, `getDownloadProgress`
- `frontend/src/routes/+layout.svelte` — amber dot on Settings nav, render SetupModal
- `frontend/src/routes/settings/+page.svelte` — complete redesign
- `frontend/src/routes/settings/page.test.ts` — updated tests

---

### Task 1: Model catalog

**Files:**
- Create: `src/videosearch/models/catalog.py`
- Create: `tests/models/test_catalog.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/models/test_catalog.py
from __future__ import annotations

import pytest
from videosearch.models.catalog import CATALOG, ModelEntry, find_by_id, get_default


def test_each_type_has_exactly_one_default():
    for model_type, entries in CATALOG.items():
        defaults = [e for e in entries if e.default]
        assert len(defaults) == 1, f"{model_type} must have exactly one default"


def test_all_entries_have_ids():
    for model_type, entries in CATALOG.items():
        for e in entries:
            assert e.id, f"{model_type} entry missing id"
            assert e.label, f"{model_type} entry missing label"
            assert e.size_label, f"{model_type} entry missing size_label"


def test_vision_entries_have_gguf_specs():
    for e in CATALOG["vision"]:
        assert e.vlm_model and "::" in e.vlm_model
        assert e.vlm_mmproj and "::" in e.vlm_mmproj
        assert e.hf_repo is None


def test_siglip_and_text_embedder_have_hf_repo():
    for model_type in ("siglip", "text_embedder"):
        for e in CATALOG[model_type]:
            assert e.hf_repo
            assert e.vlm_model is None
            assert e.vlm_mmproj is None


def test_find_by_id_returns_entry():
    entry = find_by_id("siglip", "siglip2-base")
    assert entry is not None
    assert entry.id == "siglip2-base"


def test_find_by_id_returns_none_for_unknown():
    assert find_by_id("vision", "does-not-exist") is None
    assert find_by_id("nonexistent_type", "x") is None


def test_get_default_returns_default_entry():
    entry = get_default("text_embedder")
    assert entry.default is True


def test_get_default_raises_for_unknown_type():
    with pytest.raises(KeyError):
        get_default("bogus")
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest tests/models/test_catalog.py -v
```
Expected: `ModuleNotFoundError: No module named 'videosearch.models.catalog'`

- [ ] **Step 3: Discover exact VLM filenames**

Run this to confirm the moondream2 GGUF filenames before filling in the catalog:

```bash
uv run python -c "
from huggingface_hub import list_repo_files
for f in list_repo_files('vikhyatk/moondream2'):
    if f.endswith('.gguf'):
        print(f)
"
```

Expected output: filenames ending in `.gguf` — note them. Also check LLaVA repos:

```bash
uv run python -c "
from huggingface_hub import list_repo_files
for f in list_repo_files('mys/ggml_llava-v1.5-7b'):
    if f.endswith('.gguf') or 'mmproj' in f:
        print(f)
"
```

- [ ] **Step 4: Create `catalog.py`**

Fill in the `vlm_model` and `vlm_mmproj` values using the exact filenames confirmed in Step 3. The pattern is `repo_id::filename`.

```python
# src/videosearch/models/catalog.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelEntry:
    id: str
    label: str
    size_label: str
    hf_repo: str | None       # HuggingFace repo ID — for SigLIP and text embedder
    vlm_model: str | None     # repo_id::filename — for vision GGUF model file only
    vlm_mmproj: str | None    # repo_id::filename — for vision GGUF mmproj file only
    default: bool = False


CATALOG: dict[str, list[ModelEntry]] = {
    "vision": [
        ModelEntry(
            id="moondream2",
            label="moondream2",
            size_label="~2 GB",
            hf_repo=None,
            vlm_model="vikhyatk/moondream2::moondream2-text-model-f16.gguf",
            vlm_mmproj="vikhyatk/moondream2::mmproj-moondream2-f16.gguf",
            default=True,
        ),
        ModelEntry(
            id="llava-1.5-7b",
            label="LLaVA 1.5 · 7B",
            size_label="~4 GB",
            hf_repo=None,
            vlm_model="mys/ggml_llava-v1.5-7b::ggml-model-q4_k.gguf",
            vlm_mmproj="mys/ggml_llava-v1.5-7b::mmproj-model-f16.gguf",
        ),
        ModelEntry(
            id="llava-1.5-13b",
            label="LLaVA 1.5 · 13B",
            size_label="~8 GB",
            hf_repo=None,
            vlm_model="mys/ggml_llava-v1.5-13b::ggml-model-q4_k.gguf",
            vlm_mmproj="mys/ggml_llava-v1.5-13b::mmproj-model-f16.gguf",
        ),
    ],
    "siglip": [
        ModelEntry(
            id="siglip2-base",
            label="SigLIP Base",
            size_label="~1.2 GB",
            hf_repo="google/siglip2-base-patch16-256",
            vlm_model=None,
            vlm_mmproj=None,
            default=True,
        ),
        ModelEntry(
            id="siglip2-large",
            label="SigLIP Large",
            size_label="~3.5 GB",
            hf_repo="google/siglip2-large-patch16-256",
            vlm_model=None,
            vlm_mmproj=None,
        ),
        ModelEntry(
            id="siglip-so400m",
            label="SigLIP SO400M",
            size_label="~1.6 GB",
            hf_repo="google/siglip-so400m-patch14-384",
            vlm_model=None,
            vlm_mmproj=None,
        ),
    ],
    "text_embedder": [
        ModelEntry(
            id="bge-small-en",
            label="BGE Small (English)",
            size_label="~130 MB",
            hf_repo="BAAI/bge-small-en-v1.5",
            vlm_model=None,
            vlm_mmproj=None,
            default=True,
        ),
        ModelEntry(
            id="bge-base-en",
            label="BGE Base (English)",
            size_label="~430 MB",
            hf_repo="BAAI/bge-base-en-v1.5",
            vlm_model=None,
            vlm_mmproj=None,
        ),
        ModelEntry(
            id="bge-large-en",
            label="BGE Large (English)",
            size_label="~1.3 GB",
            hf_repo="BAAI/bge-large-en-v1.5",
            vlm_model=None,
            vlm_mmproj=None,
        ),
        ModelEntry(
            id="bge-m3",
            label="BGE M3 (multilingual)",
            size_label="~2 GB",
            hf_repo="BAAI/bge-m3",
            vlm_model=None,
            vlm_mmproj=None,
        ),
    ],
}


def find_by_id(model_type: str, model_id: str) -> ModelEntry | None:
    for entry in CATALOG.get(model_type, []):
        if entry.id == model_id:
            return entry
    return None


def get_default(model_type: str) -> ModelEntry:
    for entry in CATALOG[model_type]:
        if entry.default:
            return entry
    raise ValueError(f"No default for {model_type}")
```

- [ ] **Step 5: Run tests, confirm they pass**

```bash
uv run pytest tests/models/test_catalog.py -v
```
Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add src/videosearch/models/catalog.py tests/models/test_catalog.py
git commit -m "feat: add model catalog with curated VLM, SigLIP, and text embedder presets"
```

---

### Task 2: Model downloader

**Files:**
- Create: `src/videosearch/models/downloader.py`
- Create: `tests/models/test_downloader.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/models/test_downloader.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from videosearch.models.downloader import DownloadProgress, ModelDownloader


@pytest.fixture
def downloader(tmp_path):
    return ModelDownloader(tmp_path / "models")


def test_progress_initial_state(downloader):
    p = downloader.progress()
    assert p.active is False
    assert p.model_type == ""
    assert p.model_id == ""
    assert p.downloaded_bytes == 0
    assert p.total_bytes == 0
    assert p.error is None
    assert p.complete is False


def test_is_cached_returns_false_when_nothing_cached(downloader):
    with patch("videosearch.models.downloader.try_to_load_from_cache", return_value=None):
        assert downloader.is_cached("siglip", "siglip2-base") is False


def test_is_cached_returns_true_for_hf_model_when_config_present(downloader):
    with patch("videosearch.models.downloader.try_to_load_from_cache", return_value="/some/path/config.json"):
        assert downloader.is_cached("siglip", "siglip2-base") is True


def test_is_cached_vision_requires_both_files(downloader, tmp_path):
    # Only model cached, mmproj not — should return False
    def side_effect(repo_id, filename, **kwargs):
        if "mmproj" in filename:
            return None
        return "/cached/model.gguf"

    with patch("videosearch.models.downloader.try_to_load_from_cache", side_effect=side_effect):
        assert downloader.is_cached("vision", "moondream2") is False


def test_is_cached_vision_true_when_both_files_present(downloader):
    with patch("videosearch.models.downloader.try_to_load_from_cache", return_value="/some/file.gguf"):
        assert downloader.is_cached("vision", "moondream2") is True


def test_is_cached_returns_false_for_unknown_model(downloader):
    assert downloader.is_cached("vision", "nonexistent-model") is False


def test_is_cached_returns_false_for_unknown_type(downloader):
    assert downloader.is_cached("unknown_type", "any-id") is False
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest tests/models/test_downloader.py -v
```
Expected: `ModuleNotFoundError: No module named 'videosearch.models.downloader'`

- [ ] **Step 3: Create `downloader.py`**

```python
# src/videosearch/models/downloader.py
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tqdm as tqdm_lib
from huggingface_hub import hf_hub_download, snapshot_download, try_to_load_from_cache

from videosearch.models.catalog import CATALOG, ModelEntry, find_by_id


@dataclass
class DownloadProgress:
    active: bool = False
    model_type: str = ""
    model_id: str = ""
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error: Optional[str] = None
    complete: bool = False


class ModelDownloader:
    """Runs one model download at a time in an asyncio executor. Thread-safe progress."""

    def __init__(self, models_dir: Path) -> None:
        self._models_dir = models_dir
        self._lock = threading.Lock()
        self._progress = DownloadProgress()
        self._bytes: dict[str, int] = {"downloaded": 0, "total": 0}
        self._queue: asyncio.Queue | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Call once from an asyncio context (e.g. lifespan) to start the drain loop."""
        self._queue = asyncio.Queue()
        self._task = asyncio.create_task(self._drain())

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
        """Returns True if queued, False if already cached or unknown."""
        if find_by_id(model_type, model_id) is None:
            return False
        if self.is_cached(model_type, model_id):
            return False
        assert self._queue is not None, "call start() before enqueue()"
        await self._queue.put((model_type, model_id))
        return True

    def progress(self) -> DownloadProgress:
        with self._lock:
            return DownloadProgress(
                active=self._progress.active,
                model_type=self._progress.model_type,
                model_id=self._progress.model_id,
                downloaded_bytes=self._bytes["downloaded"],
                total_bytes=self._bytes["total"],
                error=self._progress.error,
                complete=self._progress.complete,
            )

    async def _drain(self) -> None:
        assert self._queue is not None
        while True:
            model_type, model_id = await self._queue.get()
            await self._download_one(model_type, model_id)
            self._queue.task_done()

    async def _download_one(self, model_type: str, model_id: str) -> None:
        with self._lock:
            self._progress = DownloadProgress(
                active=True, model_type=model_type, model_id=model_id
            )
            self._bytes = {"downloaded": 0, "total": 0}

        entry = find_by_id(model_type, model_id)
        assert entry is not None

        try:
            loop = asyncio.get_event_loop()
            tqdm_cls = self._make_tqdm_class()

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
                    ),
                )
                await loop.run_in_executor(
                    None,
                    lambda: hf_hub_download(
                        repo2, file2,
                        cache_dir=str(self._models_dir),
                        tqdm_class=tqdm_cls,
                    ),
                )
            else:
                assert entry.hf_repo is not None
                await loop.run_in_executor(
                    None,
                    lambda: snapshot_download(entry.hf_repo, tqdm_class=tqdm_cls),
                )

            with self._lock:
                self._progress.active = False
                self._progress.complete = True

        except Exception as exc:
            with self._lock:
                self._progress.active = False
                self._progress.error = str(exc)

    def _make_tqdm_class(self):
        bytes_state = self._bytes
        lock = self._lock

        class _ProgressTqdm(tqdm_lib.tqdm):
            def update(self, n=1):
                super().update(n)
                with lock:
                    bytes_state["downloaded"] = int(self.n)
                    bytes_state["total"] = int(self.total or 0)

        return _ProgressTqdm
```

- [ ] **Step 4: Run tests, confirm they pass**

```bash
uv run pytest tests/models/test_downloader.py -v
```
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add src/videosearch/models/downloader.py tests/models/test_downloader.py
git commit -m "feat: add ModelDownloader with background asyncio queue and tqdm progress tracking"
```

---

### Task 3: `/api/models/*` endpoints + wire into app

**Files:**
- Create: `src/videosearch/api/routers/models.py`
- Create: `tests/api/test_models.py`
- Modify: `src/videosearch/api/app.py`
- Modify: `src/videosearch/api/deps.py`
- Modify: `tests/api/conftest.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_models.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from videosearch.models.downloader import DownloadProgress


def test_catalog_endpoint_returns_required_keys(client):
    r = client.get("/api/models/catalog")
    assert r.status_code == 200
    data = r.json()
    assert "first_run" in data
    assert "active_models" in data
    assert "vision" in data
    assert "siglip" in data
    assert "text_embedder" in data


def test_catalog_each_entry_has_expected_shape(client):
    r = client.get("/api/models/catalog")
    data = r.json()
    for model_type in ("vision", "siglip", "text_embedder"):
        for entry in data[model_type]:
            assert "id" in entry
            assert "label" in entry
            assert "size_label" in entry
            assert "cached" in entry
            assert "default" in entry


def test_catalog_active_models_has_three_keys(client):
    r = client.get("/api/models/catalog")
    am = r.json()["active_models"]
    assert set(am.keys()) == {"vision", "siglip", "text_embedder"}


def test_download_unknown_model_returns_404(client):
    r = client.post("/api/models/download", json={"model_type": "vision", "model_id": "bogus"})
    assert r.status_code == 404


def test_download_already_cached_returns_not_queued(client, mock_downloader):
    mock_downloader.is_cached.return_value = True
    r = client.post("/api/models/download", json={"model_type": "siglip", "model_id": "siglip2-base"})
    assert r.status_code == 200
    assert r.json()["queued"] is False


def test_download_progress_returns_progress(client, mock_downloader):
    mock_downloader.progress.return_value = DownloadProgress(
        active=True, model_type="siglip", model_id="siglip2-base",
        downloaded_bytes=100, total_bytes=1000,
    )
    r = client.get("/api/models/download/progress")
    assert r.status_code == 200
    data = r.json()
    assert data["active"] is True
    assert data["downloaded_bytes"] == 100
    assert data["total_bytes"] == 1000
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest tests/api/test_models.py -v
```
Expected: errors about missing routes

- [ ] **Step 3: Add `mock_downloader` to `tests/api/conftest.py`**

Add the new fixture and add it to the `client` fixture. The full updated file:

```python
# tests/api/conftest.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from videosearch.api import deps
from videosearch.api.app import create_app
from videosearch.config import Settings
from videosearch.models.downloader import DownloadProgress


@pytest.fixture
def test_settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", models_dir=tmp_path / "models")


@pytest.fixture
def mock_searcher():
    return MagicMock()


@pytest.fixture
def mock_jobs():
    m = MagicMock()
    m.enqueue.return_value = "test-job-id"
    return m


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
def mock_captions():
    return MagicMock()


@pytest.fixture
def mock_broadcaster():
    return MagicMock()


@pytest.fixture
def mock_worker():
    return MagicMock()


@pytest.fixture
def mock_downloader():
    m = MagicMock()
    m.is_cached.return_value = False
    m.enqueue = AsyncMock(return_value=True)
    m.progress.return_value = DownloadProgress()
    return m


@pytest.fixture
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
):
    app = create_app(test_settings, startup=False)
    app.dependency_overrides.update({
        deps.get_settings: lambda: test_settings,
        deps.get_searcher: lambda: mock_searcher,
        deps.get_jobs_queue: lambda: mock_jobs,
        deps.get_videos_repo: lambda: mock_videos,
        deps.get_frames_repo: lambda: mock_frames,
        deps.get_library_folders_repo: lambda: mock_folders,
        deps.get_captions_repo: lambda: mock_captions,
        deps.get_broadcaster: lambda: mock_broadcaster,
        deps.get_worker: lambda: mock_worker,
        deps.get_downloader: lambda: mock_downloader,
    })
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 4: Add `get_downloader` to `src/videosearch/api/deps.py`**

Add at the end of the file:

```python
def get_downloader(conn: HTTPConnection) -> "ModelDownloader":
    return conn.app.state.downloader
```

Also add the import at the top — use a string annotation to avoid circular import:

```python
# At top of deps.py, the existing imports stay; add this:
from __future__ import annotations
```

The full updated `deps.py`:

```python
# src/videosearch/api/deps.py
from __future__ import annotations

from fastapi import HTTPException
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
    if not hasattr(conn.app.state, "searcher"):
        raise HTTPException(
            status_code=503,
            detail="Models not loaded. Set vlm_model and vlm_mmproj in Settings and restart.",
        )
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


def get_downloader(conn: HTTPConnection) -> "ModelDownloader":  # noqa: F821
    return conn.app.state.downloader
```

- [ ] **Step 5: Create `src/videosearch/api/routers/models.py`**

```python
# src/videosearch/api/routers/models.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from videosearch.api.deps import get_downloader, get_settings
from videosearch.config import Settings
from videosearch.models.catalog import CATALOG, ModelEntry, find_by_id
from videosearch.models.downloader import DownloadProgress, ModelDownloader

router = APIRouter()


class CatalogEntryOut(BaseModel):
    id: str
    label: str
    size_label: str
    cached: bool
    default: bool


class CatalogResponse(BaseModel):
    first_run: bool
    active_models: dict[str, str]
    vision: list[CatalogEntryOut]
    siglip: list[CatalogEntryOut]
    text_embedder: list[CatalogEntryOut]


class DownloadRequest(BaseModel):
    model_type: str
    model_id: str


class DownloadResponse(BaseModel):
    queued: bool
    reason: str = ""


def _entry_out(entry: ModelEntry, downloader: ModelDownloader) -> CatalogEntryOut:
    return CatalogEntryOut(
        id=entry.id,
        label=entry.label,
        size_label=entry.size_label,
        cached=downloader.is_cached(entry.id if entry.hf_repo else entry.id,
                                    entry.id),  # fixed below
        default=entry.default,
    )


def _build_entry_out(model_type: str, entry: ModelEntry, downloader: ModelDownloader) -> CatalogEntryOut:
    return CatalogEntryOut(
        id=entry.id,
        label=entry.label,
        size_label=entry.size_label,
        cached=downloader.is_cached(model_type, entry.id),
        default=entry.default,
    )


def _active_model_id(model_type: str, settings: Settings) -> str:
    if model_type == "vision":
        raw = settings.vlm_model
        for entry in CATALOG["vision"]:
            if entry.vlm_model == raw:
                return entry.id
    elif model_type == "siglip":
        raw = settings.siglip_model
        for entry in CATALOG["siglip"]:
            if entry.hf_repo == raw:
                return entry.id
    elif model_type == "text_embedder":
        raw = settings.text_embedder
        for entry in CATALOG["text_embedder"]:
            if entry.hf_repo == raw:
                return entry.id
    return ""


@router.get("/models/catalog", response_model=CatalogResponse)
async def get_catalog(
    settings: Settings = Depends(get_settings),
    downloader: ModelDownloader = Depends(get_downloader),
) -> CatalogResponse:
    vision_out = [_build_entry_out("vision", e, downloader) for e in CATALOG["vision"]]
    siglip_out = [_build_entry_out("siglip", e, downloader) for e in CATALOG["siglip"]]
    te_out = [_build_entry_out("text_embedder", e, downloader) for e in CATALOG["text_embedder"]]

    any_vision_cached = any(e.cached for e in vision_out)
    any_siglip_cached = any(e.cached for e in siglip_out)
    any_te_cached = any(e.cached for e in te_out)
    first_run = not (any_vision_cached and any_siglip_cached and any_te_cached)

    active_models = {
        "vision": _active_model_id("vision", settings),
        "siglip": _active_model_id("siglip", settings),
        "text_embedder": _active_model_id("text_embedder", settings),
    }

    return CatalogResponse(
        first_run=first_run,
        active_models=active_models,
        vision=vision_out,
        siglip=siglip_out,
        text_embedder=te_out,
    )


@router.post("/models/download", response_model=DownloadResponse)
async def start_download(
    body: DownloadRequest,
    downloader: ModelDownloader = Depends(get_downloader),
) -> DownloadResponse:
    if find_by_id(body.model_type, body.model_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown model: {body.model_type}/{body.model_id}")
    if downloader.is_cached(body.model_type, body.model_id):
        return DownloadResponse(queued=False, reason="already_cached")
    await downloader.enqueue(body.model_type, body.model_id)
    return DownloadResponse(queued=True)


@router.get("/models/download/progress", response_model=DownloadProgress)
async def get_progress(
    downloader: ModelDownloader = Depends(get_downloader),
) -> DownloadProgress:
    return downloader.progress()
```

- [ ] **Step 6: Register models router and ModelDownloader in `src/videosearch/api/app.py`**

Add the import and `downloader` instantiation in `lifespan` (before the existing `if startup:` block opens the DB), and register the router. The full updated file:

```python
# src/videosearch/api/app.py
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from videosearch.api import deps
from videosearch.api.ws import JobBroadcaster, make_ws_router
from videosearch.config import Settings


def create_app(settings: Settings, *, startup: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if startup:
            from videosearch.models.downloader import ModelDownloader
            from videosearch.storage.caption_embeddings import CaptionEmbeddingsRepo
            from videosearch.storage.db import Database
            from videosearch.storage.frame_embeddings import FrameEmbeddingsRepo
            from videosearch.storage.jobs import JobsQueue
            from videosearch.storage.library_folders import LibraryFoldersRepo
            from videosearch.storage.videos import VideosRepo

            downloader = ModelDownloader(settings.models_dir)
            await downloader.start()

            db = Database(settings.data_dir)
            jobs_queue = JobsQueue(settings.data_dir / "jobs.db")
            videos = VideosRepo(db)
            frames = FrameEmbeddingsRepo(db)
            captions = CaptionEmbeddingsRepo(db)
            folders = LibraryFoldersRepo(db)

            loop = asyncio.get_running_loop()
            broadcaster = JobBroadcaster(loop)

            app.state.settings = settings
            app.state.downloader = downloader
            app.state.jobs_queue = jobs_queue
            app.state.videos_repo = videos
            app.state.frames_repo = frames
            app.state.captions_repo = captions
            app.state.library_folders_repo = folders
            app.state.broadcaster = broadcaster

            worker = None
            if settings.vlm_model and settings.vlm_mmproj:
                from videosearch.models.bge import BgeTextEmbedder
                from videosearch.models.llama_cpp_captioner import LlamaCppCaptioner
                from videosearch.models.loader import resolve_gguf
                from videosearch.models.siglip import SiglipEmbedder
                from videosearch.search import Searcher
                from videosearch.api.worker import IndexerWorker

                image_embedder = SiglipEmbedder(settings.siglip_model)
                text_embedder = BgeTextEmbedder(settings.text_embedder)
                vlm_path = resolve_gguf(settings.vlm_model, cache_dir=settings.models_dir)
                mmproj_path = resolve_gguf(settings.vlm_mmproj, cache_dir=settings.models_dir)
                captioner = LlamaCppCaptioner(
                    str(vlm_path), str(mmproj_path),
                    n_gpu_layers=settings.vlm_n_gpu_layers,
                )
                searcher = Searcher(
                    frames=frames, captions=captions,
                    image_embedder=image_embedder, text_embedder=text_embedder,
                )
                worker = IndexerWorker(
                    jobs=jobs_queue, videos=videos, frames=frames, captions=captions,
                    image_embedder=image_embedder, text_embedder=text_embedder,
                    captioner=captioner, work_dir=settings.data_dir / "work",
                    broadcaster=broadcaster, frame_fps=settings.frame_fps,
                    scene_detection=settings.scene_detection,
                )
                worker.start()
                app.state.searcher = searcher
                app.state.worker = worker

            yield

            if worker is not None:
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
    from videosearch.api.routers import models as models_router

    app.include_router(health.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(library.router, prefix="/api")
    app.include_router(ingest.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(videos.router, prefix="/api")
    app.include_router(fs.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(models_router.router, prefix="/api")
    app.include_router(make_ws_router(deps.get_broadcaster, deps.get_jobs_queue))

    _STATIC = Path(__file__).parent.parent / "static"
    if _STATIC.exists():
        app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")

    return app
```

- [ ] **Step 7: Run all tests, confirm they pass**

```bash
uv run pytest tests/ -v
```
Expected: all existing tests pass + new `test_models.py` tests pass

- [ ] **Step 8: Commit**

```bash
git add src/videosearch/models/downloader.py src/videosearch/api/routers/models.py \
        src/videosearch/api/app.py src/videosearch/api/deps.py \
        tests/api/conftest.py tests/api/test_models.py
git commit -m "feat: add /api/models/* endpoints and wire ModelDownloader into lifespan"
```

---

### Task 4: Frontend types and API client additions

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/api.test.ts`

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/lib/api.test.ts`. First read the current file to find where to append:

```typescript
// Add to the existing api.test.ts describe block (or add a new describe):
describe('models API', () => {
  it('getModelCatalog fetches /api/models/catalog', async () => {
    const mockCatalog = {
      first_run: false,
      active_models: { vision: 'moondream2', siglip: 'siglip2-base', text_embedder: 'bge-small-en' },
      vision: [{ id: 'moondream2', label: 'moondream2', size_label: '~2 GB', cached: true, default: true }],
      siglip: [],
      text_embedder: [],
    };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockCatalog), { status: 200 })
    );
    const result = await getModelCatalog();
    expect(fetch).toHaveBeenCalledWith('/api/models/catalog', undefined);
    expect(result.first_run).toBe(false);
    expect(result.vision[0].id).toBe('moondream2');
  });

  it('startModelDownload POSTs to /api/models/download', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ queued: true }), { status: 200 })
    );
    await startModelDownload('siglip', 'siglip2-base');
    expect(fetch).toHaveBeenCalledWith(
      '/api/models/download',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('getDownloadProgress fetches /api/models/download/progress', async () => {
    const mockProgress = {
      active: true, model_type: 'vision', model_id: 'moondream2',
      downloaded_bytes: 500, total_bytes: 2000, error: null, complete: false,
    };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockProgress), { status: 200 })
    );
    const result = await getDownloadProgress();
    expect(result.active).toBe(true);
    expect(result.downloaded_bytes).toBe(500);
  });
});
```

Also add imports at the top of `api.test.ts` — look at the current imports and add `getModelCatalog, startModelDownload, getDownloadProgress`.

- [ ] **Step 2: Run tests, confirm they fail**

```bash
cd frontend && npm test -- --run 2>&1 | grep -A3 "models API"
```
Expected: `getModelCatalog is not a function` (or similar import error)

- [ ] **Step 3: Add types to `frontend/src/lib/types.ts`**

Append to the end of the existing `types.ts`:

```typescript
export interface ModelCatalogEntry {
  id: string;
  label: string;
  size_label: string;
  cached: boolean;
  default: boolean;
}

export interface ModelCatalogResponse {
  first_run: boolean;
  active_models: { vision: string; siglip: string; text_embedder: string };
  vision: ModelCatalogEntry[];
  siglip: ModelCatalogEntry[];
  text_embedder: ModelCatalogEntry[];
}

export interface DownloadProgress {
  active: boolean;
  model_type: string;
  model_id: string;
  downloaded_bytes: number;
  total_bytes: number;
  error: string | null;
  complete: boolean;
}
```

- [ ] **Step 4: Add functions to `frontend/src/lib/api.ts`**

Add these imports at the top alongside existing imports:

```typescript
import type { ModelCatalogResponse, DownloadProgress } from './types';
```

Append these functions at the end of `api.ts`:

```typescript
export async function getModelCatalog(): Promise<ModelCatalogResponse> {
  return apiFetch('/api/models/catalog');
}

export async function startModelDownload(model_type: string, model_id: string): Promise<{ queued: boolean; reason?: string }> {
  return apiFetch('/api/models/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_type, model_id }),
  });
}

export async function getDownloadProgress(): Promise<DownloadProgress> {
  return apiFetch('/api/models/download/progress');
}
```

- [ ] **Step 5: Run tests, confirm they pass**

```bash
cd frontend && npm test -- --run 2>&1 | tail -5
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/lib/api.test.ts
git commit -m "feat(frontend): add model catalog types and API client functions"
```

---

### Task 5: SetupModal component

**Files:**
- Create: `frontend/src/lib/components/SetupModal.svelte`
- Create: `frontend/src/lib/components/SetupModal.test.ts`

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/lib/components/SetupModal.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import SetupModal from './SetupModal.svelte';
import * as api from '$lib/api';

vi.mock('$lib/api');
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

const catalogWithFirstRun = {
  first_run: true,
  active_models: { vision: '', siglip: '', text_embedder: '' },
  vision: [{ id: 'moondream2', label: 'moondream2', size_label: '~2 GB', cached: false, default: true }],
  siglip: [{ id: 'siglip2-base', label: 'SigLIP Base', size_label: '~1.2 GB', cached: false, default: true }],
  text_embedder: [{ id: 'bge-small-en', label: 'BGE Small (English)', size_label: '~130 MB', cached: false, default: true }],
};

const catalogAllCached = {
  first_run: false,
  active_models: { vision: 'moondream2', siglip: 'siglip2-base', text_embedder: 'bge-small-en' },
  vision: [{ id: 'moondream2', label: 'moondream2', size_label: '~2 GB', cached: true, default: true }],
  siglip: [{ id: 'siglip2-base', label: 'SigLIP Base', size_label: '~1.2 GB', cached: true, default: true }],
  text_embedder: [{ id: 'bge-small-en', label: 'BGE Small (English)', size_label: '~130 MB', cached: true, default: true }],
};

const idleProgress = {
  active: false, model_type: '', model_id: '', downloaded_bytes: 0, total_bytes: 0, error: null, complete: false,
};

beforeEach(() => {
  vi.mocked(api.startModelDownload).mockResolvedValue({ queued: true });
  vi.mocked(api.getDownloadProgress).mockResolvedValue(idleProgress);
  vi.mocked(api.getModelCatalog).mockResolvedValue(catalogWithFirstRun);
  localStorage.clear();
});

describe('SetupModal', () => {
  it('renders the welcome heading', async () => {
    render(SetupModal);
    await waitFor(() => expect(screen.getByText(/Welcome to Videosearch/i)).toBeInTheDocument());
  });

  it('shows all three model labels', async () => {
    render(SetupModal);
    await waitFor(() => {
      expect(screen.getByText(/Vision model/i)).toBeInTheDocument();
      expect(screen.getByText(/Image understanding/i)).toBeInTheDocument();
      expect(screen.getByText(/Search model/i)).toBeInTheDocument();
    });
  });

  it('calls startModelDownload for each uncached default on mount', async () => {
    render(SetupModal);
    await waitFor(() => {
      expect(api.startModelDownload).toHaveBeenCalledWith('vision', 'moondream2');
      expect(api.startModelDownload).toHaveBeenCalledWith('siglip', 'siglip2-base');
      expect(api.startModelDownload).toHaveBeenCalledWith('text_embedder', 'bge-small-en');
    });
  });

  it('sets localStorage setup_seen when all models become cached', async () => {
    // First catalog call returns first_run=true; subsequent returns all cached
    vi.mocked(api.getModelCatalog)
      .mockResolvedValueOnce(catalogWithFirstRun)
      .mockResolvedValue(catalogAllCached);
    vi.mocked(api.getDownloadProgress).mockResolvedValue({ ...idleProgress, complete: true });

    render(SetupModal);
    await waitFor(() => {
      expect(localStorage.getItem('setup_seen')).toBe('1');
    }, { timeout: 3000 });
  });
});
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
cd frontend && npm test -- --run SetupModal 2>&1 | tail -10
```
Expected: `Cannot find module './SetupModal.svelte'`

- [ ] **Step 3: Create `SetupModal.svelte`**

```svelte
<!-- frontend/src/lib/components/SetupModal.svelte -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { getModelCatalog, startModelDownload, getDownloadProgress } from '$lib/api';
  import type { ModelCatalogEntry, DownloadProgress } from '$lib/types';

  let visible = $state(true);
  let visionEntries = $state<ModelCatalogEntry[]>([]);
  let siglipEntries = $state<ModelCatalogEntry[]>([]);
  let textEntries = $state<ModelCatalogEntry[]>([]);
  let progress = $state<DownloadProgress | null>(null);
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  type ModelSection = { type: string; label: string; entry: ModelCatalogEntry | undefined };

  let sections = $derived.by<ModelSection[]>(() => [
    { type: 'vision',        label: 'Vision model',        entry: visionEntries.find(e => e.default) },
    { type: 'siglip',       label: 'Image understanding',  entry: siglipEntries.find(e => e.default) },
    { type: 'text_embedder', label: 'Search model',        entry: textEntries.find(e => e.default) },
  ]);

  function sectionStatus(section: ModelSection): 'cached' | 'downloading' | 'queued' {
    if (section.entry?.cached) return 'cached';
    if (progress?.active && progress.model_type === section.type) return 'downloading';
    return 'queued';
  }

  function pct(): number {
    if (!progress || !progress.total_bytes) return 0;
    return Math.round((progress.downloaded_bytes / progress.total_bytes) * 100);
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
      progress = await getDownloadProgress();
      if (progress.complete || !progress.active) {
        await refreshCatalog();
      }
    }, 1000);
  }

  function stopPolling() {
    if (pollInterval !== null) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  onMount(async () => {
    const catalog = await getModelCatalog();
    visionEntries = catalog.vision;
    siglipEntries = catalog.siglip;
    textEntries = catalog.text_embedder;

    // Enqueue downloads for all uncached defaults
    for (const [type, entries] of [
      ['vision', catalog.vision] as const,
      ['siglip', catalog.siglip] as const,
      ['text_embedder', catalog.text_embedder] as const,
    ]) {
      const def = entries.find(e => e.default);
      if (def && !def.cached) {
        await startModelDownload(type, def.id);
      }
    }

    startPolling();
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
                <span class="row-status downloading">{pct()}%</span>
              {:else}
                <span class="row-status queued">queued</span>
              {/if}
            </div>
            <div class="bar-track">
              {#if status === 'downloading'}
                <div class="bar-fill" style="width: {pct()}%"></div>
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
    margin-bottom: 20px;
    padding-left: 24px;
  }
  .model-rows {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-bottom: 20px;
  }
  .model-row {}
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
  .row-status {
    font-size: 9px;
  }
  .row-status.cached { color: #4ade80; }
  .row-status.downloading { color: #4ade80; }
  .row-status.queued { color: #555; }
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

- [ ] **Step 4: Run tests, confirm they pass**

```bash
cd frontend && npm test -- --run SetupModal 2>&1 | tail -8
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/components/SetupModal.svelte frontend/src/lib/components/SetupModal.test.ts
git commit -m "feat(frontend): add SetupModal with first-launch download orchestration"
```

---

### Task 6: Layout — amber nav dot + SetupModal

**Files:**
- Modify: `frontend/src/routes/+layout.svelte`

- [ ] **Step 1: Replace `+layout.svelte`**

The new layout fetches the model catalog on mount, shows an amber dot on the Settings nav link when any required model is uncached, and renders `SetupModal` on first launch (when `first_run && !localStorage.setup_seen`).

```svelte
<!-- frontend/src/routes/+layout.svelte -->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { connectJobsSocket } from '$lib/ws';
  import { getModelCatalog } from '$lib/api';
  import SetupModal from '$lib/components/SetupModal.svelte';

  let { children }: { children: Snippet } = $props();

  let setupNeeded = $state(false);
  let showModal = $state(false);

  onMount(async () => {
    const disconnect = connectJobsSocket();

    try {
      const catalog = await getModelCatalog();
      const anyVisionCached = catalog.vision.some(e => e.cached);
      const anySiglipCached = catalog.siglip.some(e => e.cached);
      const anyTeCached = catalog.text_embedder.some(e => e.cached);
      setupNeeded = !(anyVisionCached && anySiglipCached && anyTeCached);

      if (catalog.first_run && !localStorage.getItem('setup_seen')) {
        showModal = true;
      }
    } catch {
      // Server not ready — don't block app
    }

    return disconnect;
  });

  function isActive(pathname: string, href: string): boolean {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  }

  const navItems = [
    { label: 'Search', href: '/' },
    { label: 'Library', href: '/library' },
    { label: 'Jobs', href: '/jobs' },
    { label: 'Settings', href: '/settings' },
  ];
</script>

{#if showModal}
  <SetupModal />
{/if}

<div class="app">
  <nav class="navbar">
    <div class="logo">
      <div class="logo-square" aria-hidden="true"></div>
      <span class="logo-text">VIDEOSEARCH</span>
    </div>
    <div class="nav-links">
      {#each navItems as item}
        <a
          href={item.href}
          class="nav-link"
          class:active={isActive(page.url.pathname, item.href)}
          aria-current={isActive(page.url.pathname, item.href) ? 'page' : undefined}
        >
          {item.label}
          {#if item.href === '/settings' && setupNeeded}
            <span class="setup-dot" aria-label="Setup required"></span>
          {/if}
        </a>
      {/each}
    </div>
  </nav>

  <main class="main-content">
    {@render children()}
  </main>
</div>

<style>
  :global(*) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :global(body) {
    background: #0d0d0d;
    color: #e0e0e0;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 14px;
    min-height: 100vh;
  }

  :global(button) {
    cursor: pointer;
    font-family: inherit;
    font-size: inherit;
  }

  .app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  .navbar {
    background: #111;
    border-bottom: 1px solid #1e1e1e;
    padding: 10px 20px;
    display: flex;
    align-items: center;
    gap: 20px;
    flex-shrink: 0;
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .logo-square {
    width: 20px;
    height: 20px;
    background: #4ade80;
    border-radius: 4px;
  }

  .logo-text {
    font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro', monospace;
    font-size: 11px;
    color: #4ade80;
    font-weight: 700;
    letter-spacing: 0.08em;
  }

  .nav-links {
    margin-left: auto;
    display: flex;
    gap: 20px;
    align-items: center;
  }

  .nav-link {
    font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro', monospace;
    font-size: 11px;
    color: #555;
    text-decoration: none;
    padding-bottom: 2px;
    position: relative;
  }

  .nav-link.active {
    color: #4ade80;
    border-bottom: 1px solid #4ade80;
  }

  .nav-link:not(.active):hover {
    color: #888;
  }

  .setup-dot {
    position: absolute;
    top: -3px;
    right: -7px;
    width: 5px;
    height: 5px;
    background: #f59e0b;
    border-radius: 50%;
    display: inline-block;
  }

  .main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
</style>
```

- [ ] **Step 2: Run all frontend tests to check for regressions**

```bash
cd frontend && npm test -- --run 2>&1 | tail -8
```
Expected: all tests pass (layout has no test file — existing tests unaffected)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/+layout.svelte
git commit -m "feat(frontend): show SetupModal on first launch and amber dot on Settings nav"
```

---

### Task 7: Settings page redesign

**Files:**
- Modify: `frontend/src/routes/settings/+page.svelte`
- Modify: `frontend/src/routes/settings/page.test.ts`

- [ ] **Step 1: Write the new failing tests**

Replace `frontend/src/routes/settings/page.test.ts` entirely:

```typescript
// frontend/src/routes/settings/page.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import * as api from '$lib/api';

vi.mock('$lib/api');
vi.mock('$app/state', () => ({ page: { url: { pathname: '/settings' } } }));

const mockCatalog = {
  first_run: false,
  active_models: { vision: 'moondream2', siglip: 'siglip2-base', text_embedder: 'bge-small-en' },
  vision: [
    { id: 'moondream2', label: 'moondream2', size_label: '~2 GB', cached: true, default: true },
    { id: 'llava-1.5-7b', label: 'LLaVA 1.5 · 7B', size_label: '~4 GB', cached: false, default: false },
  ],
  siglip: [
    { id: 'siglip2-base', label: 'SigLIP Base', size_label: '~1.2 GB', cached: true, default: true },
  ],
  text_embedder: [
    { id: 'bge-small-en', label: 'BGE Small (English)', size_label: '~130 MB', cached: true, default: true },
  ],
};

const mockSettings = {
  frame_fps: 1.0,
  scene_detection: true,
  port: 8083,
  siglip_model: 'google/siglip2-base-patch16-256',
  text_embedder: 'BAAI/bge-small-en-v1.5',
  vlm_model: 'vikhyatk/moondream2::moondream2-text-model-f16.gguf',
  vlm_mmproj: 'vikhyatk/moondream2::mmproj-moondream2-f16.gguf',
  vlm_n_gpu_layers: -1,
};

const idleProgress = {
  active: false, model_type: '', model_id: '', downloaded_bytes: 0, total_bytes: 0, error: null, complete: false,
};

beforeEach(() => {
  vi.mocked(api.getModelCatalog).mockResolvedValue(mockCatalog);
  vi.mocked(api.getSettings).mockResolvedValue(mockSettings);
  vi.mocked(api.getDownloadProgress).mockResolvedValue(idleProgress);
  vi.mocked(api.patchSettings).mockResolvedValue({});
  vi.mocked(api.startModelDownload).mockResolvedValue({ queued: true });
});

describe('Settings page', () => {
  it('shows Vision model section heading', async () => {
    render(Page);
    await waitFor(() => expect(screen.getByText('Vision model')).toBeInTheDocument());
  });

  it('shows Image understanding section heading', async () => {
    render(Page);
    await waitFor(() => expect(screen.getByText('Image understanding')).toBeInTheDocument());
  });

  it('shows Search model section heading', async () => {
    render(Page);
    await waitFor(() => expect(screen.getByText('Search model')).toBeInTheDocument());
  });

  it('shows cached indicator for cached model', async () => {
    render(Page);
    await waitFor(() => expect(screen.getAllByText(/Cached/i).length).toBeGreaterThan(0));
  });

  it('shows Advanced options accordion', async () => {
    render(Page);
    await waitFor(() => expect(screen.getByText(/Advanced options/i)).toBeInTheDocument());
  });

  it('FPS input is inside the advanced accordion (not visible by default)', async () => {
    render(Page);
    await waitFor(() => screen.getByText(/Advanced options/i));
    // details element is closed — fps input should not be visible
    const details = screen.getByRole('group');
    expect(details).not.toHaveAttribute('open');
  });

  it('patching advanced fields uses Save button', async () => {
    render(Page);
    await waitFor(() => screen.getByText(/Advanced options/i));
    // Open the accordion
    await fireEvent.click(screen.getByText(/Advanced options/i));
    const fpsInput = await screen.findByLabelText(/frames per second/i);
    await fireEvent.input(fpsInput, { target: { value: '2' } });
    const saveBtn = screen.getByRole('button', { name: /save/i });
    await fireEvent.click(saveBtn);
    await waitFor(() => expect(api.patchSettings).toHaveBeenCalledWith(expect.objectContaining({ frame_fps: 2 })));
  });

  it('shows requires-restart hint for port', async () => {
    render(Page);
    await waitFor(() => screen.getByText(/Advanced options/i));
    await fireEvent.click(screen.getByText(/Advanced options/i));
    await waitFor(() => expect(screen.getAllByText(/requires restart/i).length).toBeGreaterThan(0));
  });
});
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
cd frontend && npm test -- --run "page.test" 2>&1 | grep -E "FAIL|pass|fail" | tail -5
```
Expected: failures (Vision model heading not found etc.)

- [ ] **Step 3: Replace `+page.svelte`**

```svelte
<!-- frontend/src/routes/settings/+page.svelte -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { getModelCatalog, getSettings, patchSettings, startModelDownload, getDownloadProgress } from '$lib/api';
  import type { ModelCatalogEntry, ModelCatalogResponse, DownloadProgress } from '$lib/types';

  // ── Catalog + settings state ──────────────────────────────────────────────
  let catalog = $state<ModelCatalogResponse | null>(null);
  let currentSettings = $state<Record<string, unknown>>({});
  let originalSettings = $state<Record<string, unknown>>({});
  let progress = $state<DownloadProgress | null>(null);

  // ── Advanced form state ───────────────────────────────────────────────────
  let saving = $state(false);
  let saved = $state(false);

  let pollInterval: ReturnType<typeof setInterval> | null = null;

  onMount(async () => {
    const [cat, settings] = await Promise.all([getModelCatalog(), getSettings()]);
    catalog = cat;
    currentSettings = { ...settings };
    originalSettings = { ...settings };
    startPolling();
  });

  onDestroy(stopPolling);

  function startPolling() {
    pollInterval = setInterval(async () => {
      progress = await getDownloadProgress();
      if (!progress.active) {
        catalog = await getModelCatalog();
      }
    }, 1500);
  }

  function stopPolling() {
    if (pollInterval !== null) { clearInterval(pollInterval); pollInterval = null; }
  }

  // ── Model selection ───────────────────────────────────────────────────────
  function selectedIdForType(type: string): string {
    if (!catalog) return '';
    if (type === 'vision') {
      const vm = currentSettings.vlm_model as string | null;
      if (!vm) return '';
      return catalog.vision.find(e => e.id !== '' && vm.startsWith(e.id.split('-')[0])) ?.id
        ?? catalog.vision.find(e => catalog!.active_models.vision === e.id)?.id ?? '';
    }
    return catalog.active_models[type as keyof typeof catalog.active_models] ?? '';
  }

  // Map catalog ID back to raw settings strings
  async function handleModelChange(type: string, newId: string) {
    if (!catalog) return;
    const entry = catalog[type as 'vision' | 'siglip' | 'text_embedder'].find(e => e.id === newId);
    if (!entry) return;

    let patch: Record<string, string> = {};
    if (type === 'vision') {
      // Resolve vlm_model and vlm_mmproj from the id via a known map
      // The catalog entries carry these as id strings; actual raw specs come from the Python catalog
      // We read them from the API by POSTing the id — the backend already knows the raw specs.
      // Instead: patchSettings accepts raw HF repo for siglip/text_embedder,
      // and the frontend needs to resolve vlm specs. Since we don't expose raw specs in the
      // catalog JSON (only label/size), we rely on a static client-side map mirroring catalog.py.
      const VLM_SPECS: Record<string, { vlm_model: string; vlm_mmproj: string }> = {
        'moondream2': {
          vlm_model: 'vikhyatk/moondream2::moondream2-text-model-f16.gguf',
          vlm_mmproj: 'vikhyatk/moondream2::mmproj-moondream2-f16.gguf',
        },
        'llava-1.5-7b': {
          vlm_model: 'mys/ggml_llava-v1.5-7b::ggml-model-q4_k.gguf',
          vlm_mmproj: 'mys/ggml_llava-v1.5-7b::mmproj-model-f16.gguf',
        },
        'llava-1.5-13b': {
          vlm_model: 'mys/ggml_llava-v1.5-13b::ggml-model-q4_k.gguf',
          vlm_mmproj: 'mys/ggml_llava-v1.5-13b::mmproj-model-f16.gguf',
        },
      };
      const specs = VLM_SPECS[newId];
      if (specs) patch = { vlm_model: specs.vlm_model, vlm_mmproj: specs.vlm_mmproj };
    } else if (type === 'siglip') {
      const SIGLIP_REPOS: Record<string, string> = {
        'siglip2-base': 'google/siglip2-base-patch16-256',
        'siglip2-large': 'google/siglip2-large-patch16-256',
        'siglip-so400m': 'google/siglip-so400m-patch14-384',
      };
      patch = { siglip_model: SIGLIP_REPOS[newId] ?? newId };
    } else if (type === 'text_embedder') {
      const BGE_REPOS: Record<string, string> = {
        'bge-small-en': 'BAAI/bge-small-en-v1.5',
        'bge-base-en': 'BAAI/bge-base-en-v1.5',
        'bge-large-en': 'BAAI/bge-large-en-v1.5',
        'bge-m3': 'BAAI/bge-m3',
      };
      patch = { text_embedder: BGE_REPOS[newId] ?? newId };
    }

    await patchSettings(patch as Record<string, unknown>);
    currentSettings = { ...currentSettings, ...patch };
    originalSettings = { ...currentSettings };

    if (!entry.cached) {
      await startModelDownload(type, newId);
    }
    catalog = await getModelCatalog();
  }

  // ── Advanced fields ───────────────────────────────────────────────────────
  function advancedTouched(): Record<string, unknown> {
    const patch: Record<string, unknown> = {};
    for (const key of ['frame_fps', 'scene_detection', 'port', 'vlm_n_gpu_layers']) {
      if (currentSettings[key] !== originalSettings[key]) {
        patch[key] = currentSettings[key];
      }
    }
    return patch;
  }

  async function handleSave(e: SubmitEvent) {
    e.preventDefault();
    saving = true;
    try {
      const patch = advancedTouched();
      if ('frame_fps' in patch) patch.frame_fps = Number(patch.frame_fps);
      if ('port' in patch) patch.port = Number(patch.port);
      if ('vlm_n_gpu_layers' in patch) patch.vlm_n_gpu_layers = Number(patch.vlm_n_gpu_layers);
      await patchSettings(patch);
      originalSettings = { ...currentSettings };
      saved = true;
      setTimeout(() => (saved = false), 2000);
    } finally {
      saving = false;
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function activeIdForType(type: string): string {
    return catalog?.active_models[type as keyof typeof catalog.active_models] ?? '';
  }

  function isDownloadingType(type: string): boolean {
    return (progress?.active ?? false) && progress?.model_type === type;
  }

  function downloadPct(): number {
    if (!progress?.total_bytes) return 0;
    return Math.round((progress.downloaded_bytes / progress.total_bytes) * 100);
  }

  function formatBytes(n: number): string {
    if (n > 1e9) return (n / 1e9).toFixed(1) + ' GB';
    if (n > 1e6) return (n / 1e6).toFixed(0) + ' MB';
    return n + ' B';
  }
</script>

<div class="page">
  <h1 class="page-title">Settings</h1>

  {#if catalog}
    <!-- ── Vision model ──────────────────────────────────────────────── -->
    <section class="model-section">
      <div class="model-label">Vision model</div>
      <p class="model-desc">Describes what's happening in each frame of your videos — the smarter the model, the better your search results.</p>
      <div class="select-row">
        <select
          class="model-select"
          value={catalog.active_models.vision || catalog.vision.find(e => e.default)?.id}
          onchange={(e) => handleModelChange('vision', (e.target as HTMLSelectElement).value)}
        >
          {#each catalog.vision as entry}
            <option value={entry.id}>{entry.label} · {entry.size_label}</option>
          {/each}
        </select>
        {#if isDownloadingType('vision')}
          <!-- progress shown below -->
        {:else}
          {@const active = catalog.vision.find(e => e.id === (catalog?.active_models.vision || catalog?.vision.find(x => x.default)?.id))}
          {#if active?.cached}
            <span class="cached-badge">● Cached</span>
          {:else}
            <span class="uncached-badge">○ Not cached</span>
          {/if}
        {/if}
      </div>
      {#if isDownloadingType('vision')}
        <div class="progress-box">
          <div class="progress-header">
            <span>Downloading…</span>
            <span class="progress-pct">{formatBytes(progress!.downloaded_bytes)} / {formatBytes(progress!.total_bytes)}</span>
          </div>
          <div class="progress-track"><div class="progress-fill" style="width:{downloadPct()}%"></div></div>
        </div>
      {/if}
      {#if activeIdForType('vision') && catalog.active_models.vision !== (catalog.vision.find(e => e.id === catalog?.active_models.vision)?.id ?? '')}
        <p class="restart-note">⚠ requires restart</p>
      {/if}
    </section>

    <!-- ── Image understanding ───────────────────────────────────────── -->
    <section class="model-section">
      <div class="model-label">Image understanding</div>
      <p class="model-desc">Recognises objects, scenes, and people in video frames so you can search visually.</p>
      <div class="select-row">
        <select
          class="model-select"
          value={catalog.active_models.siglip || catalog.siglip.find(e => e.default)?.id}
          onchange={(e) => handleModelChange('siglip', (e.target as HTMLSelectElement).value)}
        >
          {#each catalog.siglip as entry}
            <option value={entry.id}>{entry.label} · {entry.size_label}</option>
          {/each}
        </select>
        {#if isDownloadingType('siglip')}
          <!-- downloading -->
        {:else}
          {@const active = catalog.siglip.find(e => e.id === (catalog?.active_models.siglip || catalog?.siglip.find(x => x.default)?.id))}
          {#if active?.cached}
            <span class="cached-badge">● Cached</span>
          {:else}
            <span class="uncached-badge">○ Not cached</span>
          {/if}
        {/if}
      </div>
      {#if isDownloadingType('siglip')}
        <div class="progress-box">
          <div class="progress-header">
            <span>Downloading…</span>
            <span class="progress-pct">{formatBytes(progress!.downloaded_bytes)} / {formatBytes(progress!.total_bytes)}</span>
          </div>
          <div class="progress-track"><div class="progress-fill" style="width:{downloadPct()}%"></div></div>
        </div>
      {/if}
    </section>

    <!-- ── Search model ──────────────────────────────────────────────── -->
    <section class="model-section">
      <div class="model-label">Search model</div>
      <p class="model-desc">Understands your search phrases and matches them to moments in your videos.</p>
      <div class="select-row">
        <select
          class="model-select"
          value={catalog.active_models.text_embedder || catalog.text_embedder.find(e => e.default)?.id}
          onchange={(e) => handleModelChange('text_embedder', (e.target as HTMLSelectElement).value)}
        >
          {#each catalog.text_embedder as entry}
            <option value={entry.id}>{entry.label} · {entry.size_label}</option>
          {/each}
        </select>
        {#if isDownloadingType('text_embedder')}
          <!-- downloading -->
        {:else}
          {@const active = catalog.text_embedder.find(e => e.id === (catalog?.active_models.text_embedder || catalog?.text_embedder.find(x => x.default)?.id))}
          {#if active?.cached}
            <span class="cached-badge">● Cached</span>
          {:else}
            <span class="uncached-badge">○ Not cached</span>
          {/if}
        {/if}
      </div>
      {#if isDownloadingType('text_embedder')}
        <div class="progress-box">
          <div class="progress-header">
            <span>Downloading…</span>
            <span class="progress-pct">{formatBytes(progress!.downloaded_bytes)} / {formatBytes(progress!.total_bytes)}</span>
          </div>
          <div class="progress-track"><div class="progress-fill" style="width:{downloadPct()}%"></div></div>
        </div>
      {/if}
    </section>
  {:else}
    <p class="loading">Loading…</p>
  {/if}

  <!-- ── Advanced options ──────────────────────────────────────────────── -->
  <form onsubmit={handleSave} role="form">
    <details class="advanced" role="group">
      <summary class="advanced-summary">Advanced options</summary>

      <div class="advanced-fields">
        <div class="field">
          <label class="field-label" for="frame_fps">Frames per second</label>
          <input
            id="frame_fps"
            class="input"
            type="number"
            step="0.5"
            min="0.1"
            bind:value={currentSettings.frame_fps}
          />
        </div>

        <div class="field">
          <label class="field-label checkbox-label" for="scene_detection">
            <input
              id="scene_detection"
              type="checkbox"
              bind:checked={currentSettings.scene_detection as boolean}
            />
            Scene detection
          </label>
        </div>

        <div class="field">
          <label class="field-label" for="port">
            Port
            <span class="restart-hint">⚠ requires restart</span>
          </label>
          <input id="port" class="input" type="number" bind:value={currentSettings.port} />
        </div>

        <div class="field">
          <label class="field-label" for="vlm_n_gpu_layers">
            GPU layers
            <span class="field-hint">(-1 = all)</span>
          </label>
          <input id="vlm_n_gpu_layers" class="input" type="number" bind:value={currentSettings.vlm_n_gpu_layers} />
        </div>

        <div class="form-footer">
          {#if saved}<span class="saved-msg">Saved.</span>{/if}
          <button class="btn-save" type="submit" disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </details>
  </form>
</div>

<style>
  .page {
    padding: 24px 20px;
    max-width: 560px;
    display: flex;
    flex-direction: column;
    gap: 0;
  }
  .page-title {
    font-size: 16px;
    color: #e0e0e0;
    font-weight: 600;
    margin-bottom: 24px;
  }
  .model-section {
    margin-bottom: 22px;
  }
  .model-label {
    font-size: 12px;
    font-weight: 600;
    color: #e0e0e0;
    margin-bottom: 3px;
  }
  .model-desc {
    font-size: 10px;
    color: #555;
    line-height: 1.5;
    margin-bottom: 8px;
  }
  .select-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .model-select {
    flex: 1;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 11px;
    color: #e0e0e0;
    font-family: inherit;
    outline: none;
    cursor: pointer;
  }
  .model-select:focus { border-color: #4ade80; }
  .cached-badge { font-size: 10px; color: #4ade80; white-space: nowrap; }
  .uncached-badge { font-size: 10px; color: #555; white-space: nowrap; }
  .progress-box {
    background: #0f1a10;
    border: 1px solid #4ade8033;
    border-radius: 6px;
    padding: 8px 12px;
    margin-top: 6px;
  }
  .progress-header {
    display: flex;
    justify-content: space-between;
    font-size: 9px;
    color: #888;
    margin-bottom: 5px;
  }
  .progress-pct { color: #4ade80; }
  .progress-track {
    background: #1a2a1a;
    border-radius: 2px;
    height: 3px;
    overflow: hidden;
  }
  .progress-fill {
    background: #4ade80;
    height: 3px;
    border-radius: 2px;
    transition: width 0.4s ease;
  }
  .restart-note { font-size: 9px; color: #f59e0b; margin-top: 4px; }
  .loading { font-size: 11px; color: #555; }

  /* Advanced */
  .advanced {
    border-top: 1px solid #1e1e1e;
    padding-top: 14px;
    margin-top: 4px;
  }
  .advanced-summary {
    font-size: 10px;
    color: #555;
    cursor: pointer;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .advanced-summary::-webkit-details-marker { display: none; }
  .advanced-summary::before { content: '▶'; font-size: 8px; }
  details[open] .advanced-summary::before { content: '▼'; }
  .advanced-fields {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding-top: 14px;
  }
  .field { display: flex; flex-direction: column; gap: 5px; }
  .field-label {
    font-size: 11px;
    color: #888;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .checkbox-label { flex-direction: row; cursor: pointer; }
  .restart-hint { font-size: 9px; color: #f59e0b; }
  .field-hint { font-size: 9px; color: #555; }
  .input {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 12px;
    color: #e0e0e0;
    font-family: inherit;
    outline: none;
    width: 120px;
  }
  .input:focus { border-color: #4ade80; }
  .form-footer {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 12px;
    padding-top: 4px;
  }
  .saved-msg { font-size: 11px; color: #4ade80; }
  .btn-save {
    background: #4ade80;
    border: none;
    color: #000;
    font-size: 11px;
    font-weight: 700;
    padding: 7px 18px;
    border-radius: 6px;
  }
  .btn-save:disabled { opacity: 0.5; }
</style>
```

- [ ] **Step 4: Run tests, confirm they pass**

```bash
cd frontend && npm test -- --run "page.test" 2>&1 | tail -8
```
Expected: `8 passed`

- [ ] **Step 5: Run all frontend tests to check for regressions**

```bash
cd frontend && npm test -- --run 2>&1 | tail -5
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/settings/+page.svelte frontend/src/routes/settings/page.test.ts
git commit -m "feat(frontend): redesign Settings page with model dropdowns, download progress, advanced accordion"
```

---

### Task 8: Build frontend and run full test suite

**Files:**
- Modify: `src/videosearch/static/` (build output)

- [ ] **Step 1: Build the frontend**

```bash
cd frontend && npm run build 2>&1 | tail -10
```
Expected: build succeeds, `../src/videosearch/static/` updated

- [ ] **Step 2: Run all Python tests**

```bash
uv run pytest tests/ -q
```
Expected: `158 passed` (or more with new tests)

- [ ] **Step 3: Run all frontend tests**

```bash
cd frontend && npm test -- --run 2>&1 | tail -5
```
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add src/videosearch/static/
git commit -m "build: update static frontend bundle with Settings UX uplift"
```
