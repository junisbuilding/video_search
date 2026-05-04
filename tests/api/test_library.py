from __future__ import annotations

import time
from videosearch.storage.schemas import LibraryFolderRow, VideoRow


def _folder(id_: str = "f1", path: str = "/movies") -> LibraryFolderRow:
    return LibraryFolderRow(id=id_, path=path, added_at=time.time())


def _video(id_: str, status: str = "indexed", folder_id: str = "f1") -> VideoRow:
    return VideoRow(
        id=id_, path=f"/movies/{id_}.mp4", hash=id_,
        duration_sec=10.0, fps=30.0, width=1920, height=1080,
        mtime=time.time(), status=status, last_seen_at=time.time(),
        library_folder_id=folder_id,
    )


def test_list_library_returns_folders_with_counts(client, mock_folders, mock_videos):
    mock_folders.list_all.return_value = [_folder("f1")]
    mock_videos.list_by_folder.return_value = [
        _video("v1", "indexed"), _video("v2", "indexed"), _video("v3", "failed"),
    ]
    mock_videos.list_by_status.return_value = []

    r = client.get("/api/library")

    assert r.status_code == 200
    data = r.json()
    assert len(data["folders"]) == 1
    counts = data["folders"][0]["counts"]
    assert counts["indexed"] == 2
    assert counts["failed"] == 1
    assert counts["pending"] == 0


def test_register_folder_returns_400_for_nonexistent_path(client):
    r = client.post("/api/library/folders", json={"path": "/no/such/dir"})
    assert r.status_code == 400


def test_register_folder_enqueues_video_files(client, mock_folders, mock_jobs, tmp_path):
    folder = tmp_path / "movies"
    folder.mkdir()
    for name in ["a.mp4", "b.mp4"]:
        f = folder / name
        f.write_bytes(b"x" * 200_000)

    r = client.post("/api/library/folders", json={"path": str(folder)})

    assert r.status_code == 200
    data = r.json()
    assert data["enqueued"] == 2
    assert mock_jobs.enqueue.call_count == 2


def test_delete_folder_returns_404_for_unknown_id(client, mock_folders):
    mock_folders.find_by_id.return_value = None
    r = client.delete("/api/library/folders/nonexistent")
    assert r.status_code == 404


def test_delete_folder_removes_from_repo(client, mock_folders, mock_videos):
    mock_folders.find_by_id.return_value = _folder("f1")
    mock_videos.list_by_folder.return_value = []

    r = client.delete("/api/library/folders/f1")

    assert r.status_code == 200
    mock_folders.delete.assert_called_once_with("f1")


def test_rescan_enqueues_non_indexed_files(client, mock_folders, mock_jobs, tmp_path):
    folder = tmp_path / "movies"
    folder.mkdir()
    video_file = folder / "c.mp4"
    video_file.write_bytes(b"x" * 200_000)

    mock_folders.find_by_id.return_value = _folder("f1", str(folder))

    r = client.post("/api/library/folders/f1/rescan")

    assert r.status_code == 200
    assert mock_jobs.enqueue.call_count == 1


def test_register_folder_calls_add_watch(client, mock_folders, mock_jobs, mock_watcher, tmp_path):
    folder = tmp_path / "movies"
    folder.mkdir()
    (folder / "a.mp4").write_bytes(b"x" * 200_000)

    client.post("/api/library/folders", json={"path": str(folder)})

    mock_watcher.add_watch.assert_called_once()


def test_delete_folder_calls_remove_watch(client, mock_folders, mock_videos, mock_watcher):
    mock_folders.find_by_id.return_value = _folder("f1")
    mock_videos.list_by_folder.return_value = []

    client.delete("/api/library/folders/f1")

    mock_watcher.remove_watch.assert_called_once_with("f1")
