import pytest
from pathlib import Path
from videosearch.storage.downloads import DownloadStateRepo
from videosearch.storage.db import Database
from videosearch.models.downloader import ModelDownloader


@pytest.fixture
def downloader(tmp_path):
    db = Database(tmp_path / "data")
    repo = DownloadStateRepo(db)
    return ModelDownloader(tmp_path / "models", repo=repo)
