"""
Admin-only job-queue endpoints (issue #85).

* GET    /api/v1/jobs            — list recent jobs (newest first)
* GET    /api/v1/jobs/{id}       — fetch one job's status + result/error
* POST   /api/v1/jobs/{name}     — enqueue a job by registered name

The endpoints require an admin JWT (see issue #89).
"""

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth_dependencies import require_role
from src.infrastructure.queue import (
    JobNotRegisteredError,
    get_default_queue,
)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/")
def list_jobs(limit: int = 100, _: object = Depends(require_role("admin"))):
    queue = get_default_queue()
    return [j.to_dict() for j in queue.list(limit=limit)]


@router.get("/{job_id}")
def get_job(job_id: str, _: object = Depends(require_role("admin"))):
    queue = get_default_queue()
    job = queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.post("/{name}")
def enqueue_job(
    name: str,
    payload: dict | None = None,
    _: object = Depends(require_role("admin")),
):
    queue = get_default_queue()
    try:
        job = queue.enqueue(name, **(payload or {}))
    except JobNotRegisteredError:
        raise HTTPException(
            status_code=404, detail=f"Unknown job '{name}'",
        )
    return job.to_dict()
