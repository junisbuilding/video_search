import time
from pathlib import Path
from videosearch.storage.downloads import DownloadStateRepo
from videosearch.storage.db import Database

def test_create_download(tmp_path: Path):
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

def test_update_progress(tmp_path: Path):
    db = Database(tmp_path)
    repo = DownloadStateRepo(db)

    repo.create("vision", "model1", 1000)
    time.sleep(0.01)  # Ensure updated_at changes
    repo.update_progress("vision:model1", 500, 1000)

    downloads = repo.get_active()
    assert len(downloads) == 1
    assert downloads[0]["downloaded_bytes"] == 500
    assert downloads[0]["total_bytes"] == 1000
    assert downloads[0]["status"] == "downloading"
    assert downloads[0]["updated_at"] > downloads[0]["created_at"]

def test_mark_complete(tmp_path: Path):
    db = Database(tmp_path)
    repo = DownloadStateRepo(db)

    repo.create("vision", "model1", 1000)
    repo.mark_complete("vision:model1")

    downloads = repo.get_active()
    assert len(downloads) == 0

def test_mark_error(tmp_path: Path):
    db = Database(tmp_path)
    repo = DownloadStateRepo(db)

    repo.create("vision", "model1", 1000)
    repo.mark_error("vision:model1", "Network error")

    downloads = repo.get_active()
    assert len(downloads) == 0

    table = db.table("downloads")
    all_downloads = table.search().where("id = 'vision:model1'").to_list()
    assert len(all_downloads) == 1
    assert all_downloads[0]["status"] == "error"
    assert all_downloads[0]["error_message"] == "Network error"
