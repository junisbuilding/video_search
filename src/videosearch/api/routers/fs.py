from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from videosearch.scanning.skiplist import DEFAULT_VIDEO_EXTS

router = APIRouter()

_HOME = Path.home().resolve()


class FsEntry(BaseModel):
    name: str
    path: str
    kind: str  # "dir" | "video" | "other"
    size_bytes: int | None
    mtime: float


class FsListResponse(BaseModel):
    path: str
    parent: str | None
    entries: list[FsEntry]


def _safe_resolve(path_str: str | None) -> Path:
    if not path_str:
        return _HOME
    p = Path(path_str).resolve()
    if not p.is_relative_to(_HOME):
        raise HTTPException(status_code=403, detail="path outside home directory")
    return p


def _entry_kind(p: Path) -> str:
    if p.is_dir():
        return "dir"
    if p.suffix.lower() in DEFAULT_VIDEO_EXTS:
        return "video"
    return "other"


@router.get("/fs/list", response_model=FsListResponse)
async def fs_list(path: str | None = Query(default=None)) -> FsListResponse:
    resolved = _safe_resolve(path)
    if not resolved.is_dir():
        raise HTTPException(status_code=400, detail="path is not a directory")

    parent = str(resolved.parent) if resolved != _HOME else None
    entries: list[FsEntry] = []
    try:
        children = sorted(resolved.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        children = []

    for child in children:
        if child.name.startswith("."):
            continue
        try:
            stat = child.stat()
            size = stat.st_size if child.is_file() else None
            mtime = stat.st_mtime
        except OSError:
            continue
        entries.append(FsEntry(
            name=child.name,
            path=str(child),
            kind=_entry_kind(child),
            size_bytes=size,
            mtime=mtime,
        ))

    return FsListResponse(path=str(resolved), parent=parent, entries=entries)
