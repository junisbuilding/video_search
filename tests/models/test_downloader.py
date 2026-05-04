import asyncio
from pathlib import Path
from videosearch.storage.downloads import DownloadStateRepo
from videosearch.storage.db import Database
from videosearch.models.downloader import ModelDownloader

def test_restore_state_from_repo():
    tmp_path = Path("/tmp/test_downloader_restore")
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
