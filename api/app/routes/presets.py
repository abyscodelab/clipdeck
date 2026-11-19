"""Layout preset routes — configure facecam and gameplay layout coordinates for vertical clips."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import LayoutPreset, User
from app.schemas import (
    LayoutPresetCreate,
    LayoutPresetResponse,
    LayoutPresetUpdate,
    MessageResponse,
)

router = APIRouter(prefix="/api/presets", tags=["presets"])


@router.get("", response_model=list[LayoutPresetResponse])
async def list_presets(
    streamer_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(LayoutPreset)
    if streamer_id is not None:
        query = query.where(
            (LayoutPreset.streamer_id == streamer_id) | (LayoutPreset.streamer_id.is_(None))
        )
    result = await db.execute(query.order_by(LayoutPreset.is_default.desc(), LayoutPreset.name))
    return list(result.scalars().all())


@router.post("", response_model=LayoutPresetResponse, status_code=status.HTTP_201_CREATED)
async def create_preset(
    body: LayoutPresetCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    # If set to is_default and streamer_id is provided, unset other defaults for that streamer
    if body.is_default and body.streamer_id is not None:
        existing_defaults = (
            await db.execute(
                select(LayoutPreset).where(
                    LayoutPreset.streamer_id == body.streamer_id, LayoutPreset.is_default == True
                )
            )
        ).scalars().all()
        for p in existing_defaults:
            p.is_default = False

    preset = LayoutPreset(
        streamer_id=body.streamer_id,
        name=body.name,
        layout_type=body.layout_type,
        facecam_box=body.facecam_box,
        gameplay_box=body.gameplay_box,
        is_default=body.is_default,
    )
    db.add(preset)
    await db.flush()
    await db.refresh(preset)
    return preset


@router.get("/{preset_id}", response_model=LayoutPresetResponse)
async def get_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    preset = await db.scalar(select(LayoutPreset).where(LayoutPreset.id == preset_id))
    if preset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layout preset not found")
    return preset


@router.put("/{preset_id}", response_model=LayoutPresetResponse)
async def update_preset(
    preset_id: int,
    body: LayoutPresetUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    preset = await db.scalar(select(LayoutPreset).where(LayoutPreset.id == preset_id))
    if preset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layout preset not found")

    update_data = body.model_dump(exclude_unset=True)
    if update_data.get("is_default") and preset.streamer_id:
        existing_defaults = (
            await db.execute(
                select(LayoutPreset).where(
                    LayoutPreset.streamer_id == preset.streamer_id, LayoutPreset.is_default == True
                )
            )
        ).scalars().all()
        for p in existing_defaults:
            if p.id != preset.id:
                p.is_default = False

    for field, val in update_data.items():
        setattr(preset, field, val)

    await db.flush()
    await db.refresh(preset)
    return preset


@router.delete("/{preset_id}", response_model=MessageResponse)
async def delete_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    preset = await db.scalar(select(LayoutPreset).where(LayoutPreset.id == preset_id))
    if preset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layout preset not found")
    await db.delete(preset)
    await db.flush()
    return MessageResponse(message=f"Layout preset '{preset.name}' deleted")
