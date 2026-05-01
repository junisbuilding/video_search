from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from videosearch.api.deps import get_jobs_queue
from videosearch.storage.jobs import Job, JobsQueue

router = APIRouter()


class JobResponse(BaseModel):
    id: str
    video_id: str | None
    path: str | None
    kind: str
    status: str
    progress: float
    error: str | None
    created_at: float
    updated_at: float


class JobsListResponse(BaseModel):
    jobs: list[JobResponse]


def _job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id, video_id=job.video_id, path=job.path,
        kind=job.kind, status=job.status, progress=job.progress,
        error=job.error, created_at=job.created_at, updated_at=job.updated_at,
    )


@router.get("/jobs", response_model=JobsListResponse)
async def list_jobs(
    jobs: JobsQueue = Depends(get_jobs_queue),
) -> JobsListResponse:
    return JobsListResponse(jobs=[_job_to_response(j) for j in jobs.list_recent(200)])


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    jobs: JobsQueue = Depends(get_jobs_queue),
) -> dict:
    job = jobs.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="only failed jobs can be retried")
    new_id = jobs.enqueue(
        kind=job.kind,
        path=job.path,
        library_folder_id=job.library_folder_id,
    )
    return {"job_id": new_id}
