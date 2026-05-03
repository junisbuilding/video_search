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
