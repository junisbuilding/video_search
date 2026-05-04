import time
from pathlib import Path
from videosearch.storage.downloads import DownloadStateRepo
from videosearch.storage.db import Database

def test_create_download():
    tmp_path = Path("/tmp/test_downloads")
    db = Database(tmp_path)
    repo = DownloadStateRepo(db)

    repo.create("vision", "model1", 1000)

    downloads = repo.get_active()
    assert len(downloads) == 1
    assert downloads[0]["id"] == "vision:model1"
    assert downloads[0]["model_type"] == "vision"
    assert downloads[0]["model_id"] == "model1"
    assert downloads[0]["downloaded_bytes"] == 0
    assert downloads[0]["total_bytes"] == 1000
    assert downloads[0]["status"] == "queued"
