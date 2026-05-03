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
                await asyncio.gather(
                    loop.run_in_executor(
                        None,
                        lambda: hf_hub_download(
                            repo1, file1,
                            cache_dir=str(self._models_dir),
                            tqdm_class=tqdm_cls,
                            token=self._token,
                        ),
                    ),
                    loop.run_in_executor(
                        None,
                        lambda: hf_hub_download(
                            repo2, file2,
                            cache_dir=str(self._models_dir),
                            tqdm_class=tqdm_cls,
                            token=self._token,
                        ),
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
