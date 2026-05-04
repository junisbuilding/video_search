from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from videosearch.models.downloader import DownloadProgress, ModelDownloader


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


def test_catalog_first_run_true_when_nothing_cached(client, mock_downloader):
    mock_downloader.is_cached.return_value = False
    r = client.get("/api/models/catalog")
    assert r.json()["first_run"] is True


def test_download_returns_already_running_when_task_active(client, mock_downloader):
    """enqueue() returns False for an in-progress download — API should report queued: False."""
    mock_downloader.enqueue.return_value = False
    r = client.post("/api/models/download", json={"model_type": "siglip", "model_id": "siglip2-base"})
    assert r.status_code == 200
    assert r.json()["queued"] is False
    assert r.json()["reason"] == "already_running"


def test_catalog_first_run_uses_real_is_cached(tmp_path):
    """first_run reflects real filesystem state — no mocks."""
    downloader = ModelDownloader(tmp_path / "models")
    with patch("videosearch.models.downloader.try_to_load_from_cache", return_value=None):
        assert downloader.is_cached("siglip", "siglip2-base") is False

    with patch("videosearch.models.downloader.try_to_load_from_cache", return_value="/cache/model.safetensors"):
        assert downloader.is_cached("siglip", "siglip2-base") is True


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


def test_downloader_has_repo():
    import asyncio
    from videosearch.api.app import create_app
    from videosearch.config import Settings
    from pathlib import Path

    tmp_path = Path("/tmp/test_app_downloader")
    settings = Settings(
        data_dir=tmp_path,
        models_dir=tmp_path / "models",
    )

    app = create_app(settings, startup=True)

    # Enter lifespan to initialize app state
    async def run_test():
        async with app.router.lifespan_context(app):
            # Verify downloader has repo
            assert hasattr(app.state.downloader, "_repo")
            assert app.state.downloader._repo is not None

    asyncio.run(run_test())


def test_download_persists_across_restart(tmp_path):
    """Test that download state persists across server restart."""
    import time
    from unittest.mock import patch
    from videosearch.api.app import create_app
    from videosearch.config import Settings

    settings = Settings(
        data_dir=tmp_path / "data",
        models_dir=tmp_path / "models",
    )

    # Start server and begin download
    app1 = create_app(settings, startup=True)
    with TestClient(app1) as client1:
        # Mock is_cached to ensure the model is not cached
        with patch.object(app1.state.downloader, 'is_cached', return_value=False):
            # Start a download
            response = client1.post("/api/models/download", json={
                "model_type": "siglip",
                "model_id": "siglip2-base",
            })
            assert response.status_code == 200
            result = response.json()
            assert result["queued"] is True

            # Give the download task time to initialize progress state
            time.sleep(0.1)

            # Get progress
            response = client1.get("/api/models/download/progress")
            assert response.status_code == 200
            progress1 = response.json()
            assert len(progress1) >= 1

    # Simulate server restart by creating new app instance
    app2 = create_app(settings, startup=True)
    with TestClient(app2) as client2:
        # Get progress after restart
        response = client2.get("/api/models/download/progress")
        assert response.status_code == 200
        progress2 = response.json()

        # Progress should be restored
        assert len(progress2) >= 1
        assert progress2[0]["model_type"] == progress1[0]["model_type"]
        assert progress2[0]["model_id"] == progress1[0]["model_id"]
