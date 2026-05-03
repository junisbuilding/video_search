from __future__ import annotations

from unittest.mock import patch

import pytest

from videosearch.models.downloader import DownloadProgress, ModelDownloader


@pytest.fixture
def downloader(tmp_path):
    return ModelDownloader(tmp_path / "models")


def test_progress_returns_empty_list_initially(downloader):
    assert downloader.progress() == []


def test_is_cached_returns_false_when_nothing_cached(downloader):
    with patch("videosearch.models.downloader.try_to_load_from_cache", return_value=None):
        assert downloader.is_cached("siglip", "siglip2-base") is False


def test_is_cached_returns_true_for_hf_model_when_config_present(downloader):
    with patch("videosearch.models.downloader.try_to_load_from_cache", return_value="/some/path/config.json"):
        assert downloader.is_cached("siglip", "siglip2-base") is True


def test_is_cached_vision_requires_both_files(downloader):
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


@pytest.mark.anyio
async def test_enqueue_already_cached_skips(downloader):
    await downloader.start()
    with patch("videosearch.models.downloader.try_to_load_from_cache", return_value="/cached/config.json"):
        queued = await downloader.enqueue("siglip", "siglip2-base")
    assert queued is False
    assert downloader.progress() == []


@pytest.mark.anyio
async def test_token_passed_to_hf_hub_download(tmp_path, monkeypatch):
    captured: list[dict] = []

    def fake_hf_hub_download(*args, **kwargs):
        captured.append(kwargs)
        return str(tmp_path / "fake.gguf")

    monkeypatch.setattr("videosearch.models.downloader.hf_hub_download", fake_hf_hub_download)

    downloader = ModelDownloader(tmp_path, token="hf_test_token")
    await downloader.start()
    await downloader._download_one("vision", "moondream2")

    assert any(c.get("token") == "hf_test_token" for c in captured)


@pytest.mark.anyio
async def test_concurrent_downloads_create_separate_tasks(tmp_path, monkeypatch):
    """enqueue() fires an independent task per model — no serial blocking."""
    def fake_hf_hub_download(*args, **kwargs):
        return str(tmp_path / "fake.gguf")

    def fake_snapshot_download(*args, **kwargs):
        return str(tmp_path / "fake_snapshot")

    monkeypatch.setattr("videosearch.models.downloader.hf_hub_download", fake_hf_hub_download)
    monkeypatch.setattr("videosearch.models.downloader.snapshot_download", fake_snapshot_download)
    monkeypatch.setattr("videosearch.models.downloader.try_to_load_from_cache", lambda *a, **kw: None)

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
    monkeypatch.setattr("videosearch.models.downloader.try_to_load_from_cache", lambda *a, **kw: None)

    downloader = ModelDownloader(tmp_path)
    await downloader.start()

    await downloader.enqueue("siglip", "siglip2-base")
    await downloader._tasks[("siglip", "siglip2-base")]

    result = downloader.progress()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].model_type == "siglip"
    assert result[0].complete is True
