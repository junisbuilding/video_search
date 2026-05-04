from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from videosearch.api.deps import (
    get_jobs_queue,
    get_library_folders_repo,
    get_library_watcher,
    get_videos_repo,
)
from videosearch.scanning.skiplist import should_skip
from videosearch.scanning.watcher import LibraryWatcher
from videosearch.storage.jobs import JobsQueue
from videosearch.storage.library_folders import LibraryFoldersRepo
from videosearch.storage.schemas import LibraryFolderRow
from videosearch.storage.videos import VideosRepo

router = APIRouter()


class RegisterFolderRequest(BaseModel):
    path: str


class FolderCounts(BaseModel):
    indexed: int
    pending: int
    failed: int
    missing: int


class FolderResponse(BaseModel):
    id: str
    path: str
    added_at: float
    counts: FolderCounts


class LibraryResponse(BaseModel):
    folders: list[FolderResponse]
    ad_hoc_counts: FolderCounts


class RegisterFolderResponse(BaseModel):
    folder: FolderResponse
    enqueued: int


def _counts(videos: list) -> FolderCounts:
    c: dict[str, int] = {"indexed": 0, "pending": 0, "failed": 0, "missing": 0}
    for v in videos:
        if v.status in c:
            c[v.status] += 1
    return FolderCounts(**c)


def _walk_and_enqueue(path: Path, folder_id: str | None, jobs: JobsQueue) -> int:
    count = 0
    for f in path.rglob("*"):
        if not f.is_file():
            continue
        if should_skip(f):
            continue
        jobs.enqueue(kind="index", path=str(f), library_folder_id=folder_id)
        count += 1
    return count


@router.get("/library", response_model=LibraryResponse)
async def list_library(
    folders: LibraryFoldersRepo = Depends(get_library_folders_repo),
    videos: VideosRepo = Depends(get_videos_repo),
) -> LibraryResponse:
    folder_rows = folders.list_all()
    folder_responses: list[FolderResponse] = []
    for folder in folder_rows:
        vids = videos.list_by_folder(folder.id)
        folder_responses.append(FolderResponse(
            id=folder.id, path=folder.path, added_at=folder.added_at,
            counts=_counts(vids),
        ))
    ad_hoc = videos.list_by_folder(None)
    return LibraryResponse(folders=folder_responses, ad_hoc_counts=_counts(ad_hoc))


@router.post("/library/folders", response_model=RegisterFolderResponse)
async def register_folder(
    body: RegisterFolderRequest,
    folders: LibraryFoldersRepo = Depends(get_library_folders_repo),
    jobs: JobsQueue = Depends(get_jobs_queue),
    watcher: LibraryWatcher = Depends(get_library_watcher),
) -> RegisterFolderResponse:
    path = Path(body.path)
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="path is not a directory")

    folder_id = str(uuid.uuid4())
    folder = LibraryFolderRow(id=folder_id, path=str(path), added_at=time.time())
    folders.insert(folder)

    count = await asyncio.to_thread(_walk_and_enqueue, path, folder_id, jobs)
    watcher.add_watch(folder_id, path)
    return RegisterFolderResponse(
        folder=FolderResponse(
            id=folder.id, path=folder.path, added_at=folder.added_at,
            counts=_counts([]),
        ),
        enqueued=count,
    )


@router.delete("/library/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    purge: bool = False,
    folders: LibraryFoldersRepo = Depends(get_library_folders_repo),
    videos: VideosRepo = Depends(get_videos_repo),
    watcher: LibraryWatcher = Depends(get_library_watcher),
) -> dict:
    folder = folders.find_by_id(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="folder not found")
    if purge:
        for video in videos.list_by_folder(folder_id):
            videos.update(video.id, status="missing")
    watcher.remove_watch(folder_id)
    folders.delete(folder_id)
    return {"ok": True}


@router.post("/library/folders/{folder_id}/rescan")
async def rescan_folder(
    folder_id: str,
    folders: LibraryFoldersRepo = Depends(get_library_folders_repo),
    jobs: JobsQueue = Depends(get_jobs_queue),
) -> dict:
    folder = folders.find_by_id(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="folder not found")
    count = await asyncio.to_thread(
        _walk_and_enqueue, Path(folder.path), folder_id, jobs
    )
    return {"enqueued": count}
