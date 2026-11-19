"""Streamer CRUD routes + manual clip trigger."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Moment, Streamer, User
from app.schemas import (
    MessageResponse,
    MomentResponse,
    StreamerCreate,
    StreamerResponse,
    StreamerUpdate,
)
from app.services.job_service import create_job
from app.services.sse_service import broadcaster

router = APIRouter(prefix="/api/streamers", tags=["streamers"])


@router.get("", response_model=list[StreamerResponse])
async def list_streamers(
    platform: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(Streamer)
    if platform:
        query = query.where(Streamer.platform == platform)
    query = query.order_by(Streamer.priority.desc(), Streamer.name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=StreamerResponse, status_code=status.HTTP_201_CREATED)
async def create_streamer(
    body: StreamerCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    streamer = Streamer(**body.model_dump())
    db.add(streamer)
    await db.flush()
    await db.refresh(streamer)
    await broadcaster.publish("streamer_status", {"streamer_id": streamer.id, "action": "created", "name": streamer.name})
    return streamer


@router.get("/{streamer_id}", response_model=StreamerResponse)
async def get_streamer(
    streamer_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Streamer).where(Streamer.id == streamer_id))
    streamer = result.scalar_one_or_none()
    if streamer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Streamer not found")
    return streamer


@router.put("/{streamer_id}", response_model=StreamerResponse)
async def update_streamer(
    streamer_id: int,
    body: StreamerUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Streamer).where(Streamer.id == streamer_id))
    streamer = result.scalar_one_or_none()
    if streamer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Streamer not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(streamer, field, value)
    await db.flush()
    await db.refresh(streamer)
    return streamer


@router.delete("/{streamer_id}", response_model=MessageResponse)
async def delete_streamer(
    streamer_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Streamer).where(Streamer.id == streamer_id))
    streamer = result.scalar_one_or_none()
    if streamer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Streamer not found")
    await db.delete(streamer)
    await db.flush()
    return MessageResponse(message=f"Streamer '{streamer.name}' deleted")


@router.post("/{streamer_id}/clip-now", response_model=MomentResponse, status_code=status.HTTP_201_CREATED)
async def clip_now(
    streamer_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Manually trigger a clip for a streamer."""
    result = await db.execute(select(Streamer).where(Streamer.id == streamer_id))
    streamer = result.scalar_one_or_none()
    if streamer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Streamer not found")

    moment = Moment(
        streamer_id=streamer_id,
        hype_score=0.0,
        status="detected",
        trigger_type="manual",
    )
    db.add(moment)
    await db.flush()
    await db.refresh(moment)

    # Create a render job for this manual clip
    await create_job(
        db,
        queue="render",
        job_type="manual_clip",
        params={"streamer_id": streamer_id, "moment_id": moment.id},
        streamer_id=streamer_id,
        moment_id=moment.id,
    )

    await broadcaster.publish(
        "new_moment",
        {"moment_id": moment.id, "streamer_id": streamer_id, "trigger": "manual"},
    )
    return moment
