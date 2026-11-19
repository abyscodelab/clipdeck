"""Job routes — list, get, retry, cancel."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import JobResponse, MessageResponse
from app.services.job_service import cancel_job, get_job, list_jobs, retry_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_all_jobs(
    queue: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    jobs, _total = await list_jobs(db, queue=queue, status=status_filter, page=page, page_size=page_size)
    return jobs


@router.get("/{job_id}", response_model=JobResponse)
async def get_single_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    job = await get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_single_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    job = await retry_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not found or not in a retryable state (must be failed or cancelled)",
        )
    return job


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_single_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    job = await cancel_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not found or not in a cancellable state (must be pending or running)",
        )
    return job
