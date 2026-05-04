from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from videosearch.models.downloader import DownloadProgress, ModelDownloader
from videosearch.storage.db import Database
from videosearch.storage.downloads import DownloadStateRepo


def test_restore_state_from_repo(downloader, tmp_path):
    # Write a mid-download record to the same DB the fixture uses.
    db = Database(tmp_path / "data")
    repo = DownloadStateRepo(db)
    repo.create("siglip", "siglip2-base", 1000)
    repo.update_progress("siglip:siglip2-base", 500, 1000)

    asyncio.run(downloader.start())

    progress = downloader.progress()
    assert len(progress) == 1
    assert progress[0].model_type == "siglip"
    assert progress[0].model_id == "siglip2-base"
    assert progress[0].downloaded_bytes == 500
    assert progress[0].total_bytes == 1000


def test_restore_state_marks_interrupted(downloader, tmp_path):
    """Records left active from a previous session are shown as interrupted, not in-flight."""
    db = Database(tmp_path / "data")
    repo = DownloadStateRepo(db)
    repo.create("siglip", "siglip2-base", 1000)
    repo.update_progress("siglip:siglip2-base", 500, 1000)

    asyncio.run(downloader.start())

    progress = downloader.progress()
    assert not progress[0].active
    assert progress[0].error == "interrupted by server restart"

    # Repo record should be marked as error so cleanup can collect it.
    active = downloader._repo.get_active()
    assert len(active) == 0


def test_progress_persisted_during_download(downloader):
    """tqdm update writes bytes to the repo record."""
    downloader._repo.create("siglip", "siglip2-base", 1000)
    bytes_state: dict[str, int] = {"downloaded": 0, "total": 0}
    lock = threading.Lock()
    tqdm_cls = downloader._make_tqdm_class(bytes_state, lock, "siglip:siglip2-base")

    bar = tqdm_cls(total=1000)
    bar.update(500)
    bar.close()

    downloads = downloader._repo.get_active()
    assert len(downloads) == 1
    assert downloads[0]["downloaded_bytes"] == 500
    assert downloads[0]["status"] == "downloading"


def test_completion_persisted_to_repo(downloader):
    """Successful _download_one marks the repo record complete."""
    with patch("videosearch.models.downloader.snapshot_download"):
        asyncio.run(downloader._download_one("siglip", "siglip2-base"))

    active = downloader._repo.get_active()
    assert len(active) == 0

    table = downloader._repo._db.table("downloads")
    rows = table.search().where("id = 'siglip:siglip2-base'").to_list()
    assert rows[0]["status"] == "complete"


def test_error_persisted_to_repo(downloader):
    """Failed _download_one marks the repo record as error with message."""
    with patch("videosearch.models.downloader.snapshot_download", side_effect=RuntimeError("network error")):
        asyncio.run(downloader._download_one("siglip", "siglip2-base"))

    active = downloader._repo.get_active()
    assert len(active) == 0

    table = downloader._repo._db.table("downloads")
    rows = table.search().where("id = 'siglip:siglip2-base'").to_list()
    assert rows[0]["status"] == "error"
    assert "network error" in rows[0]["error_message"]


def test_vision_download_passes_tqdm_to_hf_hub_download(downloader):
    """hf_hub_download for vision models receives the tqdm class so progress is tracked."""
    with patch("videosearch.models.downloader.hf_hub_download") as mock_dl:
        asyncio.run(downloader._download_one("vision", "moondream2"))

    assert mock_dl.call_count == 2
    for call in mock_dl.call_args_list:
        assert "tqdm_class" in call.kwargs


def test_create_is_idempotent(downloader):
    """Calling create() twice for the same id replaces the row, not duplicates it."""
    downloader._repo.create("siglip", "siglip2-base", 1000)
    downloader._repo.create("siglip", "siglip2-base", 2000)

    table = downloader._repo._db.table("downloads")
    rows = table.search().where("id = 'siglip:siglip2-base'").to_list()
    assert len(rows) == 1
    assert rows[0]["total_bytes"] == 2000
