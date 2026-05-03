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
