from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from videosearch.api.deps import get_jobs_queue
from videosearch.scanning.skiplist import should_skip
from videosearch.storage.jobs import JobsQueue

router = APIRouter()


class IngestRequest(BaseModel):
    path: str
    recursive: bool = True


class IngestResponse(BaseModel):
    enqueued: list[str]


def _collect_and_enqueue(path: Path, recursive: bool, jobs: JobsQueue) -> list[str]:
    job_ids: list[str] = []
    if path.is_file():
        if not should_skip(path):
            job_ids.append(jobs.enqueue(kind="index", path=str(path)))
        return job_ids

    glob = path.rglob("*") if recursive else path.glob("*")
    for f in glob:
        if not f.is_file():
            continue
        if should_skip(f):
            continue
        job_ids.append(jobs.enqueue(kind="index", path=str(f)))
    return job_ids


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    body: IngestRequest,
    jobs: JobsQueue = Depends(get_jobs_queue),
) -> IngestResponse:
    path = Path(body.path)
    if not path.exists():
        raise HTTPException(status_code=400, detail="path does not exist")
    job_ids = await asyncio.to_thread(_collect_and_enqueue, path, body.recursive, jobs)
    return IngestResponse(enqueued=job_ids)
