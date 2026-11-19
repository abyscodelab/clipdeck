"""Render task: Executes deterministic FFmpeg 9:16 vertical render from EDL."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select

from clipdeck.shared import constants
from clipdeck.shared.ai.edl_schema import EditDecisionList
from clipdeck.shared.render.renderer import RenderResult, VerticalVideoRenderer
from clipdeck.shared.transcription.base import WordTimestamp

logger = logging.getLogger(__name__)


async def _publish_event(redis: Any, event_type: str, data: dict[str, Any]) -> None:
    if redis is None:
        return
    try:
        payload = json.dumps({"event": event_type, "data": data})
        await redis.publish("clipdeck_events", payload)
    except Exception as e:
        logger.debug("Failed to publish event to Redis: %s", e)


async def render_clip_task(
    ctx: dict[str, Any],
    clip_id: int,
) -> dict[str, Any]:
    """Execute FFmpeg render pipeline for a Clip using its latest EditVersion."""
    logger.info("Starting render_clip_task for clip_id=%d", clip_id)
    db_session_factory = ctx.get("db_session_factory")
    redis = ctx.get("redis")
    media_path = Path(ctx.get("media_path") or constants.DEFAULT_MEDIA_PATH)

    if not db_session_factory:
        return {"status": "error", "error": "db_session_factory missing"}

    from app.models import Clip, EditVersion, Moment  # type: ignore

    async with db_session_factory() as session:
        clip = await session.get(Clip, clip_id)
        if not clip:
            return {"status": "error", "error": f"Clip {clip_id} not found"}

        clip.status = "rendering"
        await session.commit()

        # Fetch latest edit version
        stmt = (
            select(EditVersion)
            .where(EditVersion.clip_id == clip_id)
            .order_by(EditVersion.version_number.desc())
        )
        res = await session.execute(stmt)
        latest_version = res.scalars().first()
        if not latest_version or not latest_version.edl_data:
            return {"status": "error", "error": f"No EDL data found for clip {clip_id}"}

        edl = EditDecisionList(**latest_version.edl_data)

        # Fetch raw video file and transcript from Moment
        moment = await session.get(Moment, clip.moment_id) if clip.moment_id else None
        if not moment or not moment.file_path:
            return {"status": "error", "error": "Source moment video file missing"}

        input_video_path = Path(moment.file_path)
        if not input_video_path.exists():
            return {"status": "error", "error": f"Source video does not exist: {input_video_path}"}

        # Extract words from transcript if available
        chat_data = moment.chat_data or {}
        transcript_raw = chat_data.get("transcript") or {}
        words = [WordTimestamp(**w) for w in transcript_raw.get("words", [])]

    # Destination paths
    clips_dir = media_path / constants.CLIPS_DIR
    clips_dir.mkdir(parents=True, exist_ok=True)
    output_video_path = clips_dir / f"vertical_{clip.streamer_id}_{clip_id}.mp4"

    renderer = VerticalVideoRenderer(fps=30)
    try:
        render_result: RenderResult = await renderer.render(
            input_video_path=input_video_path,
            edl=edl,
            words=words,
            output_path=output_video_path,
        )

        async with db_session_factory() as session:
            clip = await session.get(Clip, clip_id)
            if clip:
                clip.file_path = str(render_result.file_path)
                clip.thumbnail_path = (
                    str(render_result.thumbnail_path) if render_result.thumbnail_path else None
                )
                clip.duration = render_result.duration
                clip.status = "rendered"
                await session.commit()

        logger.info(
            "Successfully rendered 9:16 vertical short for clip %d: %s (%.1fs)",
            clip_id, render_result.file_path, render_result.duration,
        )

        await _publish_event(redis, "clip_rendered", {
            "clip_id": clip_id,
            "moment_id": clip.moment_id,
            "file_path": str(render_result.file_path),
            "thumbnail_path": str(render_result.thumbnail_path) if render_result.thumbnail_path else None,
            "duration": render_result.duration,
            "file_size": render_result.file_size,
        })

        return {
            "status": "completed",
            "clip_id": clip_id,
            "file_path": str(render_result.file_path),
            "duration": render_result.duration,
        }

    except Exception as e:
        logger.error("Rendering failed for clip %d: %s", clip_id, e)
        async with db_session_factory() as session:
            clip = await session.get(Clip, clip_id)
            if clip:
                clip.status = "failed"
                await session.commit()
        return {"status": "error", "error": str(e)}
