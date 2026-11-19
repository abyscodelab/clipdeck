"""Moment routes — list, get, update status."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Moment, User
from app.schemas import MomentResponse, MomentStatusUpdate
from app.services.sse_service import broadcaster

router = APIRouter(prefix="/api/moments", tags=["moments"])


@router.get("", response_model=list[MomentResponse])
async def list_moments(
    streamer_id: int | None = None,
    session_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    trigger_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(Moment)
    if streamer_id is not None:
        query = query.where(Moment.streamer_id == streamer_id)
    if session_id is not None:
        query = query.where(Moment.session_id == session_id)
    if status_filter:
        query = query.where(Moment.status == status_filter)
    if trigger_type:
        query = query.where(Moment.trigger_type == trigger_type)
    query = query.order_by(Moment.detected_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{moment_id}", response_model=MomentResponse)
async def get_moment(
    moment_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Moment).where(Moment.id == moment_id))
    moment = result.scalar_one_or_none()
    if moment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moment not found")
    return moment


@router.put("/{moment_id}/status", response_model=MomentResponse)
async def update_moment_status(
    moment_id: int,
    body: MomentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Moment).where(Moment.id == moment_id))
    moment = result.scalar_one_or_none()
    if moment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moment not found")

    old_status = moment.status
    moment.status = body.status
    await db.flush()
    await db.refresh(moment)

    await broadcaster.publish(
        "new_moment",
        {"moment_id": moment.id, "old_status": old_status, "new_status": body.status},
    )
    return moment
