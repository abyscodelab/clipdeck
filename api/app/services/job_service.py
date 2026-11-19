"""Job service — create, query, update, retry, cancel jobs."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job
from app.services.sse_service import broadcaster


async def create_job(
    db: AsyncSession,
    *,
    queue: str,
    job_type: str,
    params: dict[str, Any] | None = None,
    max_retries: int = 3,
    streamer_id: int | None = None,
    moment_id: int | None = None,
) -> Job:
    """Insert a new job and broadcast the event."""
    job = Job(
        queue=queue,
        job_type=job_type,
        status="pending",
        params=params,
        max_retries=max_retries,
        streamer_id=streamer_id,
        moment_id=moment_id,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    await broadcaster.publish("job_update", {"job_id": job.id, "status": "pending", "queue": queue})
    return job


async def get_job(db: AsyncSession, job_id: int) -> Job | None:
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def list_jobs(
    db: AsyncSession,
    *,
    queue: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Job], int]:
    """Return paginated jobs with optional filters."""
    query = select(Job)
    count_query = select(func.count(Job.id))

    if queue:
        query = query.where(Job.queue == queue)
        count_query = count_query.where(Job.queue == queue)
    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Job.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def retry_job(db: AsyncSession, job_id: int) -> Job | None:
    """Reset a failed job for retry."""
    job = await get_job(db, job_id)
    if job is None or job.status not in ("failed", "cancelled"):
        return None
    job.status = "pending"
    job.retries += 1
    job.error = None
    job.progress = 0.0
    job.started_at = None
    job.completed_at = None
    await db.flush()
    await db.refresh(job)
    await broadcaster.publish("job_update", {"job_id": job.id, "status": "pending", "action": "retry"})
    return job


async def cancel_job(db: AsyncSession, job_id: int) -> Job | None:
    """Cancel a pending or running job."""
    job = await get_job(db, job_id)
    if job is None or job.status not in ("pending", "running"):
        return None
    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(job)
    await broadcaster.publish("job_update", {"job_id": job.id, "status": "cancelled"})
    return job
