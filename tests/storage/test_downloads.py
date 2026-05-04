import threading
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

def test_cleanup_completed(tmp_path: Path):
    db = Database(tmp_path)
    repo = DownloadStateRepo(db)

    repo.create("vision", "model1", 1000)
    repo.create("siglip", "model2", 2000)
    repo.create("text_embedder", "model3", 3000)

    repo.mark_complete("vision:model1")
    repo.mark_error("siglip:model2", "Test error")

    table = db.table("downloads")
    old_time = time.time() - 7200
    table.update(where="id = 'vision:model1'", values={"updated_at": old_time})

    repo.cleanup_completed()

    downloads = repo.get_active()
    assert len(downloads) == 1
    assert downloads[0]["id"] == "text_embedder:model3"

def test_concurrent_updates(tmp_path: Path):
    db = Database(tmp_path)
    repo = DownloadStateRepo(db)

    repo.create("vision", "model1", 1000)

    errors = []
    def update_progress(i):
        try:
            repo.update_progress("vision:model1", i * 100, 1000)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=update_progress, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0

    downloads = repo.get_active()
    assert len(downloads) == 1
    assert downloads[0]["total_bytes"] == 1000
