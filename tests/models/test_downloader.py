from __future__ import annotations

from unittest.mock import patch

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
    assert downloader.progress().active is False


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
