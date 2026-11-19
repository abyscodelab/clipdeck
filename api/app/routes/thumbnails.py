"""Vertical Thumbnail Generation API Routes.

Implements GTA VI-style 1080x1920 vertical thumbnails with dual modes:
- 'cinematic': Red / Blue police rim lighting + Miami night background
- 'split': 3D clay + wireframe AI scan half + black & white divider
Huge 2-word condensed title behind the hero character.
"""

from __future__ import annotations

import base64
import io
import os
import re
import time
from pathlib import Path
from typing import Literal, Optional

import cv2
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Clip, User
from shared.media.gta_vertical_thumbnail import (
    build_vertical_thumbnail,
    extract_hook_words,
)

router = APIRouter(prefix="/api/thumbnails", tags=["thumbnails"])


class GenerateThumbnailRequest(BaseModel):
    clip_id: Optional[int] = Field(None, description="Clip ID to attach this thumbnail to")
    word1: Optional[str] = Field(None, description="First impact word (White)")
    word2: Optional[str] = Field(None, description="Second impact word (Red #EB1923)")
    mode: Literal["cinematic", "split"] = Field("cinematic", description="Style mode")
    face_x: float = Field(0.5, ge=0.0, le=1.0, description="Horizontal nose split fraction")
    badge_title: str = Field("GTA VI", description="Top badge primary title")
    badge_sub: str = Field("CLIPPED", description="Top badge subtitle")
    hero_base64: Optional[str] = Field(None, description="Optional base64 PNG data for custom cutout")


class ThumbnailResponse(BaseModel):
    thumbnail_url: str
    file_path: str
    mode: str
    word1: str
    word2: str
    clip_id: Optional[int]
    width: int = 1080
    height: int = 1920
    created_at: float


class ThumbnailListItem(BaseModel):
    filename: str
    thumbnail_url: str
    clip_id: Optional[int]
    mode: str
    word1: str
    word2: str
    size_bytes: int
    created_at: float


def _extract_video_keyframe(video_path: str | Path) -> Optional[Image.Image]:
    """Extract a representative keyframe from a video using OpenCV."""
    if not os.path.exists(video_path):
        return None
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    # Pick frame at ~30% into video
    target_idx = max(0, min(total_frames - 1, int(total_frames * 0.3)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return None
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(frame_rgb)


@router.get("", response_model=list[ThumbnailListItem])
async def list_thumbnails(
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
):
    """List all generated 1080x1920 vertical thumbnails."""
    thumb_dir = Path(settings.MEDIA_STORAGE_PATH) / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    items = []
    files = sorted(thumb_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files[:limit]:
        # Parse metadata from filename if possible
        # convention: thumb_{clip_id}_{mode}_{w1}_{w2}_{ts}.jpg
        parts = f.stem.split("_")
        clip_id = None
        mode = "cinematic"
        w1, w2 = "GTA", "SHORT"
        if len(parts) >= 6 and parts[0] == "thumb":
            try:
                clip_id = int(parts[1]) if parts[1] != "custom" else None
                mode = parts[2]
                w1 = parts[3]
                w2 = parts[4]
            except Exception:
                pass

        items.append(
            ThumbnailListItem(
                filename=f.name,
                thumbnail_url=f"/media/thumbnails/{f.name}",
                clip_id=clip_id,
                mode=mode,
                word1=w1,
                word2=w2,
                size_bytes=f.stat().st_size,
                created_at=f.stat().st_mtime,
            )
        )
    return items


@router.post("/generate", response_model=ThumbnailResponse)
async def generate_thumbnail(
    body: GenerateThumbnailRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a vertical GTA VI-style thumbnail with custom or auto-derived parameters."""
    clip = None
    if body.clip_id:
        result = await db.execute(select(Clip).where(Clip.id == body.clip_id))
        clip = result.scalar_one_or_none()
        if not clip:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")

    # Determine 1-2 impact words
    w1 = body.word1
    w2 = body.word2
    if not w1 or not w2:
        title_source = clip.title if clip and clip.title else "INSANE CLUTCH MOMENT"
        extracted_w1, extracted_w2 = extract_hook_words(title_source)
        w1 = w1 or extracted_w1
        w2 = w2 or extracted_w2

    # Determine hero character image
    hero_image: Optional[Image.Image] = None
    if body.hero_base64:
        try:
            # Strip header if present
            data_str = body.hero_base64
            if "," in data_str:
                data_str = data_str.split(",", 1)[1]
            raw_bytes = base64.b64decode(data_str)
            hero_image = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid hero image: {e}")
    elif clip and clip.file_path and os.path.exists(clip.file_path):
        # Extract frame from clip video
        hero_image = _extract_video_keyframe(clip.file_path)

    # Output path
    thumb_dir = Path(settings.MEDIA_STORAGE_PATH) / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    clip_tag = str(clip.id) if clip else "custom"
    safe_w1 = re.sub(r"\W+", "", w1)[:10]
    safe_w2 = re.sub(r"\W+", "", w2)[:10]
    filename = f"thumb_{clip_tag}_{body.mode}_{safe_w1}_{safe_w2}_{ts}.jpg"
    out_path = thumb_dir / filename

    # Build the vertical thumbnail
    build_vertical_thumbnail(
        out_path=out_path,
        word1=w1,
        word2=w2,
        hero_image=hero_image,
        mode=body.mode,
        face_x=body.face_x,
        badge_title=body.badge_title,
        badge_sub=body.badge_sub,
    )

    thumb_url = f"/media/thumbnails/{filename}"

    # If linked to clip, update clip record
    if clip:
        clip.thumbnail_path = str(out_path)
        await db.commit()

    return ThumbnailResponse(
        thumbnail_url=thumb_url,
        file_path=str(out_path),
        mode=body.mode,
        word1=w1,
        word2=w2,
        clip_id=clip.id if clip else None,
        created_at=time.time(),
    )


@router.post("/clips/{clip_id}/auto-thumbnail", response_model=ThumbnailResponse)
async def auto_generate_for_clip(
    clip_id: int,
    mode: Literal["cinematic", "split"] = Query("cinematic"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """One-click trigger to auto-generate and assign a vertical GTA VI thumbnail for a clip."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")

    w1, w2 = extract_hook_words(clip.title or "INSANE MOMENT")

    hero_image = None
    if clip.file_path and os.path.exists(clip.file_path):
        hero_image = _extract_video_keyframe(clip.file_path)

    thumb_dir = Path(settings.MEDIA_STORAGE_PATH) / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    safe_w1 = re.sub(r"\W+", "", w1)[:10]
    safe_w2 = re.sub(r"\W+", "", w2)[:10]
    filename = f"thumb_{clip.id}_{mode}_{safe_w1}_{safe_w2}_{ts}.jpg"
    out_path = thumb_dir / filename

    build_vertical_thumbnail(
        out_path=out_path,
        word1=w1,
        word2=w2,
        hero_image=hero_image,
        mode=mode,
        badge_title="GTA VI",
        badge_sub="CLIPPED",
    )

    thumb_url = f"/media/thumbnails/{filename}"
    clip.thumbnail_path = str(out_path)
    await db.commit()

    return ThumbnailResponse(
        thumbnail_url=thumb_url,
        file_path=str(out_path),
        mode=mode,
        word1=w1,
        word2=w2,
        clip_id=clip.id,
        created_at=time.time(),
    )
