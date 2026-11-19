"""Stream session routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import ChatStatsBucket, StreamSession, User
from app.schemas import ChatStatsBucketResponse, StreamSessionResponse

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[StreamSessionResponse])
async def list_sessions(
    streamer_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(StreamSession)
    if streamer_id is not None:
        query = query.where(StreamSession.streamer_id == streamer_id)
    if status_filter:
        query = query.where(StreamSession.status == status_filter)
    query = query.order_by(StreamSession.started_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{session_id}", response_model=StreamSessionResponse)
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(StreamSession).where(StreamSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.get("/{session_id}/stats", response_model=list[ChatStatsBucketResponse])
async def get_session_stats(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Return all chat stats buckets for a session."""
    # Verify session exists
    sess_result = await db.execute(select(StreamSession).where(StreamSession.id == session_id))
    if sess_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    result = await db.execute(
        select(ChatStatsBucket)
        .where(ChatStatsBucket.session_id == session_id)
        .order_by(ChatStatsBucket.timestamp)
    )
    return list(result.scalars().all())
