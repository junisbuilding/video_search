from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from watchdog.events import (
    DirCreatedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
)

from videosearch.scanning.watcher import FolderEventHandler, LibraryWatcher, WatchStatus
from videosearch.storage.schemas import VideoRow


def _video_row(id_: str, path: str) -> VideoRow:
    now = time.time()
    return VideoRow(
        id=id_, path=path, hash=id_, duration_sec=10.0, fps=30.0,
        width=320, height=240, mtime=now, status="indexed", last_seen_at=now,
    )


class TestFolderEventHandler:
    def setup_method(self):
        self.jobs = MagicMock()
        self.videos = MagicMock()
        self.handler = FolderEventHandler("folder-1", self.jobs, self.videos)

    def test_on_created_enqueues_video(self, tmp_path):
        path = tmp_path / "movie.mp4"
        path.write_bytes(b"x" * 200_000)
        self.handler.on_created(FileCreatedEvent(str(path)))
        self.jobs.enqueue.assert_called_once_with(
            kind="index", path=str(path), library_folder_id="folder-1"
        )

    def test_on_created_skips_dotfile(self, tmp_path):
        path = tmp_path / ".hidden.mp4"
        path.write_bytes(b"x" * 200_000)
        self.handler.on_created(FileCreatedEvent(str(path)))
        self.jobs.enqueue.assert_not_called()

    def test_on_created_skips_non_video_extension(self, tmp_path):
        path = tmp_path / "notes.txt"
        path.write_bytes(b"x" * 200_000)
        self.handler.on_created(FileCreatedEvent(str(path)))
        self.jobs.enqueue.assert_not_called()

    def test_on_created_ignores_directory_event(self):
        self.handler.on_created(DirCreatedEvent("/some/dir"))
        self.jobs.enqueue.assert_not_called()

    def test_on_modified_enqueues_video(self, tmp_path):
        path = tmp_path / "movie.mp4"
        path.write_bytes(b"x" * 200_000)
        self.handler.on_modified(FileModifiedEvent(str(path)))
        self.jobs.enqueue.assert_called_once_with(
            kind="index", path=str(path), library_folder_id="folder-1"
        )

    def test_on_deleted_marks_known_video_missing(self):
        path = "/videos/movie.mp4"
        self.videos.find_by_path.return_value = _video_row("v1", path)
        self.handler.on_deleted(FileDeletedEvent(path))
        self.videos.find_by_path.assert_called_once_with(path)
        self.videos.update.assert_called_once_with("v1", status="missing")

    def test_on_deleted_does_nothing_for_unknown_path(self):
        self.videos.find_by_path.return_value = None
        self.handler.on_deleted(FileDeletedEvent("/videos/movie.mp4"))
        self.videos.update.assert_not_called()

    def test_on_deleted_skips_non_video_name(self):
        self.handler.on_deleted(FileDeletedEvent("/videos/notes.txt"))
        self.videos.find_by_path.assert_not_called()

    def test_on_deleted_skips_bundle_path(self):
        self.handler.on_deleted(FileDeletedEvent("/Photos.photoslibrary/Masters/clip.mp4"))
        self.videos.find_by_path.assert_not_called()

    def test_on_moved_marks_src_missing_and_enqueues_dst(self, tmp_path):
        src = "/videos/old.mp4"
        dst = tmp_path / "new.mp4"
        dst.write_bytes(b"x" * 200_000)
        self.videos.find_by_path.return_value = _video_row("v1", src)
        self.handler.on_moved(FileMovedEvent(src, str(dst)))
        self.videos.update.assert_called_once_with("v1", status="missing")
        self.jobs.enqueue.assert_called_once_with(
            kind="index", path=str(dst), library_folder_id="folder-1"
        )


class TestLibraryWatcher:
    def test_status_empty_initially(self):
        watcher = LibraryWatcher(MagicMock(), MagicMock())
        watcher.start()
        try:
            assert watcher.status() == []
        finally:
            watcher.stop()

    def test_add_watch_records_active_status(self, tmp_path):
        watcher = LibraryWatcher(MagicMock(), MagicMock())
        watcher.start()
        try:
            watcher.add_watch("folder-1", tmp_path)
            statuses = watcher.status()
            assert len(statuses) == 1
            assert statuses[0].folder_id == "folder-1"
            assert statuses[0].path == str(tmp_path)
            assert statuses[0].active is True
            assert statuses[0].error is None
        finally:
            watcher.stop()

    def test_remove_watch_clears_status(self, tmp_path):
        watcher = LibraryWatcher(MagicMock(), MagicMock())
        watcher.start()
        try:
            watcher.add_watch("folder-1", tmp_path)
            watcher.remove_watch("folder-1")
            assert watcher.status() == []
        finally:
            watcher.stop()

    def test_add_watch_oserror_records_error(self, tmp_path):
        watcher = LibraryWatcher(MagicMock(), MagicMock())
        watcher.start()
        try:
            with patch.object(watcher._observer, "schedule", side_effect=OSError("inotify limit")):
                watcher.add_watch("folder-1", tmp_path)
            statuses = watcher.status()
            assert len(statuses) == 1
            assert statuses[0].active is False
            assert statuses[0].error is not None
            assert "inotify limit" in statuses[0].error
        finally:
            watcher.stop()

    def test_add_watch_idempotent(self, tmp_path):
        watcher = LibraryWatcher(MagicMock(), MagicMock())
        watcher.start()
        try:
            with patch.object(watcher._observer, "schedule", wraps=watcher._observer.schedule) as mock_schedule:
                watcher.add_watch("folder-1", tmp_path)
                watcher.add_watch("folder-1", tmp_path)
                assert mock_schedule.call_count == 1
            assert len(watcher.status()) == 1
        finally:
            watcher.stop()
