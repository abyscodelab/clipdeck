"""Clip routes — list, create, detail, update, rerender."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Clip, EditVersion, Moment, Streamer, User
from app.schemas import (
    ClipCreate,
    ClipDetailResponse,
    ClipRerenderRequest,
    ClipResponse,
    ClipUpdate,
    MessageResponse,
)
from app.services.job_service import create_job
from app.services.sse_service import broadcaster

router = APIRouter(prefix="/api/clips", tags=["clips"])


@router.get("/subtle-styles")
async def get_subtle_styles():
    """Return all 39 Subtle animated caption styles with metadata."""
    from clipdeck.shared.render.subtle_engine import SubtleEngine

    engine = SubtleEngine()
    return engine.list_styles()


@router.get("", response_model=list[ClipResponse])
async def list_clips(
    streamer_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(Clip)
    if streamer_id is not None:
        query = query.where(Clip.streamer_id == streamer_id)
    if status_filter:
        query = query.where(Clip.status == status_filter)

    query = query.order_by(desc(Clip.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=ClipDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_clip(
    body: ClipCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    # Verify streamer exists
    streamer = await db.scalar(select(Streamer).where(Streamer.id == body.streamer_id))
    if not streamer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Streamer not found")

    clip = Clip(
        moment_id=body.moment_id,
        streamer_id=body.streamer_id,
        title=body.title,
        description=body.description,
        hashtags=body.hashtags,
        duration=body.duration,
        status=body.status,
        aspect_ratio=body.aspect_ratio,
    )
    db.add(clip)
    await db.flush()
    await db.refresh(clip)

    # If edl_data provided, create initial EditVersion
    if body.edl_data:
        edit_ver = EditVersion(
            clip_id=clip.id,
            version_number=1,
            edl_data=body.edl_data,
            ai_reasoning=body.ai_reasoning,
            model_used=body.model_used,
        )
        db.add(edit_ver)
        await db.flush()

    # Trigger render job if status is rendering
    if clip.status == "rendering":
        await create_job(
            db,
            queue="render",
            job_type="render_clip",
            params={"clip_id": clip.id, "streamer_id": clip.streamer_id},
            streamer_id=clip.streamer_id,
            moment_id=clip.moment_id,
        )

    await broadcaster.publish(
        "clip_update",
        {"clip_id": clip.id, "streamer_id": clip.streamer_id, "status": clip.status},
    )

    # Reload with relationships
    stmt = (
        select(Clip)
        .options(selectinload(Clip.edit_versions), selectinload(Clip.playbook_traces))
        .where(Clip.id == clip.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()


@router.get("/{clip_id}", response_model=ClipDetailResponse)
async def get_clip(
    clip_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    stmt = (
        select(Clip)
        .options(selectinload(Clip.edit_versions), selectinload(Clip.playbook_traces))
        .where(Clip.id == clip_id)
    )
    result = await db.execute(stmt)
    clip = result.scalar_one_or_none()
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    return clip


@router.put("/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: int,
    body: ClipUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    clip = await db.scalar(select(Clip).where(Clip.id == clip_id))
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(clip, field, val)

    await db.flush()
    await db.refresh(clip)
    return clip


@router.post("/{clip_id}/rerender", response_model=ClipDetailResponse)
async def rerender_clip(
    clip_id: int,
    body: ClipRerenderRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Trigger a re-render of a clip with new EDL or preset overrides."""
    stmt = (
        select(Clip)
        .options(selectinload(Clip.edit_versions), selectinload(Clip.playbook_traces))
        .where(Clip.id == clip_id)
    )
    result = await db.execute(stmt)
    clip = result.scalar_one_or_none()
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")

    if body.aspect_ratio:
        clip.aspect_ratio = body.aspect_ratio

    # Calculate next version number
    next_ver_num = len(clip.edit_versions) + 1
    new_edl = body.edl_data or (clip.edit_versions[-1].edl_data if clip.edit_versions else {})

    edit_ver = EditVersion(
        clip_id=clip.id,
        version_number=next_ver_num,
        edl_data=new_edl,
        ai_reasoning=f"User triggered rerender (version {next_ver_num})",
        model_used=None,
    )
    db.add(edit_ver)
    clip.status = "rendering"
    await db.flush()

    # Create render job
    await create_job(
        db,
        queue="render",
        job_type="rerender_clip",
        params={
            "clip_id": clip.id,
            "version_number": next_ver_num,
            "layout_preset_id": body.layout_preset_id,
            "aspect_ratio": clip.aspect_ratio,
        },
        streamer_id=clip.streamer_id,
        moment_id=clip.moment_id,
    )

    await broadcaster.publish(
        "job_update",
        {"clip_id": clip.id, "action": "rerender", "version": next_ver_num},
    )

    result = await db.execute(stmt)
    return result.scalar_one()
