from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from videosearch.scanning.skiplist import DEFAULT_BUNDLE_SUFFIXES, DEFAULT_VIDEO_EXTS, should_skip
from videosearch.storage.jobs import JobsQueue
from videosearch.storage.videos import VideosRepo


@dataclass(frozen=True)
class WatchStatus:
    folder_id: str
    path: str
    active: bool
    error: str | None


def _is_video_by_name(path: Path) -> bool:
    """Check if path looks like a video file by name alone (no filesystem access)."""
    if path.name.startswith("."):
        return False
    if any(part.endswith(DEFAULT_BUNDLE_SUFFIXES) for part in path.parts):
        return False
    return path.suffix.lower() in DEFAULT_VIDEO_EXTS


class FolderEventHandler(FileSystemEventHandler):
    def __init__(self, folder_id: str, jobs: JobsQueue, videos: VideosRepo) -> None:
        super().__init__()
        self._folder_id = folder_id
        self._jobs = jobs
        self._videos = videos

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if should_skip(path):
            return
        self._jobs.enqueue(kind="index", path=str(path), library_folder_id=self._folder_id)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if should_skip(path):
            return
        self._jobs.enqueue(kind="index", path=str(path), library_folder_id=self._folder_id)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        # File no longer exists — can't call should_skip(). Check name only.
        if not _is_video_by_name(path):
            return
        video = self._videos.find_by_path(str(path))
        if video is not None:
            self._videos.update(video.id, status="missing")

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        src = Path(event.src_path)
        dst = Path(event.dest_path)  # type: ignore[attr-defined]
        if _is_video_by_name(src):
            video = self._videos.find_by_path(str(src))
            if video is not None:
                self._videos.update(video.id, status="missing")
        if not should_skip(dst):
            self._jobs.enqueue(kind="index", path=str(dst), library_folder_id=self._folder_id)


class LibraryWatcher:
    def __init__(self, jobs: JobsQueue, videos: VideosRepo) -> None:
        self._jobs = jobs
        self._videos = videos
        self._observer = Observer()
        self._watches: dict[str, object] = {}
        self._status: dict[str, WatchStatus] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join()

    def add_watch(self, folder_id: str, path: str | Path) -> None:
        with self._lock:
            if folder_id in self._watches:
                return
        handler = FolderEventHandler(folder_id, self._jobs, self._videos)
        try:
            watch = self._observer.schedule(handler, str(path), recursive=True)
            with self._lock:
                self._watches[folder_id] = watch
                self._status[folder_id] = WatchStatus(
                    folder_id=folder_id, path=str(path), active=True, error=None,
                )
        except OSError as exc:
            with self._lock:
                self._status[folder_id] = WatchStatus(
                    folder_id=folder_id, path=str(path), active=False,
                    error=f"{exc} — on Linux run: sudo sysctl fs.inotify.max_user_watches=524288",
                )

    def remove_watch(self, folder_id: str) -> None:
        with self._lock:
            watch = self._watches.pop(folder_id, None)
            self._status.pop(folder_id, None)
        if watch is not None:
            self._observer.unschedule(watch)  # type: ignore[arg-type]

    def status(self) -> list[WatchStatus]:
        with self._lock:
            return list(self._status.values())
