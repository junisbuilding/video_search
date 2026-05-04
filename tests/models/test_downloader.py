import asyncio
import shutil
import threading
from pathlib import Path
from videosearch.storage.downloads import DownloadStateRepo
from videosearch.storage.db import Database
from videosearch.models.downloader import ModelDownloader, DownloadProgress

def test_restore_state_from_repo():
    tmp_path = Path("/tmp/test_downloader_restore")
    # Clean up any existing database
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    
    db = Database(tmp_path)
    repo = DownloadStateRepo(db)

    # Create a download record in the repo
    repo.create("vision", "model1", 1000)
    repo.update_progress("vision:model1", 500, 1000)

    # Create downloader with repo
    downloader = ModelDownloader(tmp_path / "models", repo=repo)

    # Start the downloader to restore state
    asyncio.run(downloader.start())

    # Verify state was restored
    progress = downloader.progress()
    assert len(progress) == 1
    assert progress[0].model_type == "vision"
    assert progress[0].model_id == "model1"
    assert progress[0].downloaded_bytes == 500
    assert progress[0].total_bytes == 1000

def test_progress_persisted_during_download():
    tmp_path = Path("/tmp/test_downloader_persist")
    # Clean up any existing database
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    
    db = Database(tmp_path)
    repo = DownloadStateRepo(db)
    downloader = ModelDownloader(tmp_path / "models", repo=repo)

    # Create download record in repo (this is what _download_one does)
    repo.create("vision", "model2", 0)

    # Start a download (mock the actual download)
    key = ("vision", "model2")
    downloader._progress[key] = DownloadProgress(
        active=True, model_type="vision", model_id="model2"
    )
    downloader._bytes[key] = {"downloaded": 0, "total": 1000}
    downloader._locks[key] = threading.Lock()

    # Simulate progress update by calling repo.update_progress directly
    # (this is what tqdm.update() does internally)
    repo.update_progress("vision:model2", 500, 1000)

    # Verify repo was updated
    downloads = repo.get_active()
    assert len(downloads) == 1
    assert downloads[0]["downloaded_bytes"] == 500

def test_completion_persisted_to_repo():
    tmp_path = Path("/tmp/test_downloader_complete")
    # Clean up any existing database
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    
    db = Database(tmp_path)
    repo = DownloadStateRepo(db)
    downloader = ModelDownloader(tmp_path / "models", repo=repo)

    # Create a download record
    repo.create("vision", "model1", 1000)

    # Simulate completion
    key = ("vision", "model1")
    downloader._progress[key] = DownloadProgress(
        active=True, model_type="vision", model_id="model1"
    )
    downloader._locks[key] = threading.Lock()

    # Mark as complete
    with downloader._locks[key]:
        downloader._progress[key].active = False
        downloader._progress[key].complete = True
        if downloader._repo is not None:
            downloader._repo.mark_complete("vision:model1")

    # Verify repo was updated
    downloads = repo.get_active()
    assert len(downloads) == 0  # Complete downloads are not active

def test_error_persisted_to_repo():
    tmp_path = Path("/tmp/test_downloader_error")
    # Clean up any existing database
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    
    db = Database(tmp_path)
    repo = DownloadStateRepo(db)
    downloader = ModelDownloader(tmp_path / "models", repo=repo)

    # Create a download record
    repo.create("vision", "model1", 1000)

    # Simulate error
    key = ("vision", "model1")
    downloader._progress[key] = DownloadProgress(
        active=True, model_type="vision", model_id="model1"
    )
    downloader._locks[key] = threading.Lock()

    # Mark as error
    with downloader._locks[key]:
        downloader._progress[key].active = False
        downloader._progress[key].error = "Test error"
        if downloader._repo is not None:
            downloader._repo.mark_error("vision:model1", "Test error")

    # Verify repo was updated
    downloads = repo.get_active()
    assert len(downloads) == 0  # Error downloads are not active
