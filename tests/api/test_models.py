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


def test_catalog_first_run_false_when_all_types_cached(client, mock_downloader):
    mock_downloader.is_cached.return_value = True
    r = client.get("/api/models/catalog")
    assert r.status_code == 200
    assert r.json()["first_run"] is False


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
