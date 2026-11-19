"""Clip tasks: automated clipping of detected moments and on-demand manual clipping."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from clipdeck.shared import constants
from clipdeck.shared.media.clipper import ClipResult, cut_clip
from clipdeck.shared.media.ring_buffer import RingBufferRecorder

logger = logging.getLogger(__name__)


def _find_segments_on_disk(buffer_dir: Path, streamer_id: int, start_time: float, end_time: float) -> list[Path]:
    """Helper to locate ring buffer segments directly from disk when recorder is not in memory."""
    if not buffer_dir.exists():
        return []

    pattern = re.compile(rf"^{streamer_id}_(\d+)\.ts$")
    segments: list[tuple[float, Path]] = []
    for p in buffer_dir.iterdir():
        m = pattern.match(p.name)
        if m:
            segments.append((float(m.group(1)), p))

    segments.sort(key=lambda x: x[0])
    if not segments:
        return []

    matched: list[Path] = []
    for i, (ts, path) in enumerate(segments):
        seg_start = ts
        seg_end = segments[i + 1][0] if i + 1 < len(segments) else ts + constants.SEGMENT_DURATION_SECS
        if seg_end >= start_time and seg_start <= end_time:
            matched.append(path)

    return matched


async def _publish_event(redis: Any, event_type: str, data: dict[str, Any]) -> None:
    if redis is None:
        return
    try:
        payload = json.dumps({"event": event_type, "data": data})
        await redis.publish("clipdeck_events", payload)
    except Exception as e:
        logger.debug("Failed to publish event to Redis: %s", e)


async def clip_moment(
    ctx: dict[str, Any],
    moment_id: int,
) -> dict[str, Any]:
    """Render a clip for a detected Moment from the ring buffer."""
    logger.info("Starting clip_moment job for moment_id=%d", moment_id)
    db_session_factory = ctx.get("db_session_factory")
    redis = ctx.get("redis")
    media_path = Path(ctx.get("media_path") or constants.DEFAULT_MEDIA_PATH)

    if not db_session_factory:
        logger.error("Database session factory missing in context")
        return {"status": "error", "error": "db_session_factory missing"}

    from app.models import Moment  # type: ignore

    # 1. Fetch moment from DB
    async with db_session_factory() as session:
        moment = await session.get(Moment, moment_id)
        if not moment:
            return {"status": "error", "error": f"Moment {moment_id} not found"}

        streamer_id = moment.streamer_id
        start_time = moment.clip_start_time or (time.time() - 45.0)
        end_time = moment.clip_end_time or time.time()
        peak_time = (start_time + end_time) / 2.0

        moment.status = "clipping"
        await session.commit()

    # 2. Locate segments in ring buffer
    recorders: dict[int, RingBufferRecorder] = ctx.get("recorders", {})
    recorder = recorders.get(streamer_id)

    if recorder:
        segments = recorder.get_segment_range(start_time, end_time)
    else:
        buffer_dir = media_path / constants.RING_BUFFER_DIR / str(streamer_id)
        segments = _find_segments_on_disk(buffer_dir, streamer_id, start_time, end_time)

    if not segments:
        logger.error(
            "No segments found for streamer %d in window [%.1f, %.1f]",
            streamer_id, start_time, end_time,
        )
        async with db_session_factory() as session:
            moment = await session.get(Moment, moment_id)
            if moment:
                moment.status = "error"
                await session.commit()
        return {"status": "error", "error": "No ring buffer segments available"}

    # 3. Render clip
    clip_dir = media_path / constants.CLIPS_DIR
    clip_dir.mkdir(parents=True, exist_ok=True)
    out_file = clip_dir / f"clip_{streamer_id}_{moment_id}_{int(start_time)}.mp4"

    try:
        clip_result: ClipResult = await cut_clip(
            segments=segments,
            start_time=start_time,
            end_time=end_time,
            output_path=out_file,
            thumbnail_time=peak_time,
        )

        # 4. Update moment with result
        async with db_session_factory() as session:
            moment = await session.get(Moment, moment_id)
            if moment:
                moment.file_path = str(clip_result.file_path)
                moment.thumbnail_path = (
                    str(clip_result.thumbnail_path) if clip_result.thumbnail_path else None
                )
                moment.clip_duration = clip_result.duration
                moment.status = "clipped"
                await session.commit()

        logger.info(
            "Successfully created clip for moment %d: %s (%.1fs)",
            moment_id, clip_result.file_path, clip_result.duration,
        )

        # 5. Broadcast SSE event
        await _publish_event(redis, "moment_clipped", {
            "moment_id": moment_id,
            "streamer_id": streamer_id,
            "file_path": str(clip_result.file_path),
            "thumbnail_path": str(clip_result.thumbnail_path) if clip_result.thumbnail_path else None,
            "duration": clip_result.duration,
            "file_size": clip_result.file_size,
        })

        return {
            "status": "clipped",
            "moment_id": moment_id,
            "file_path": str(clip_result.file_path),
            "duration": clip_result.duration,
        }

    except Exception as e:
        logger.error("Error cutting clip for moment %d: %s", moment_id, e)
        async with db_session_factory() as session:
            moment = await session.get(Moment, moment_id)
            if moment:
                moment.status = "error"
                await session.commit()
        return {"status": "error", "error": str(e)}


async def manual_clip(
    ctx: dict[str, Any],
    streamer_id: int,
    duration_seconds: int = 30,
) -> dict[str, Any]:
    """Immediately clip the last N seconds of a stream."""
    logger.info("Executing manual_clip for streamer %d (duration=%ds)", streamer_id, duration_seconds)
    now = time.time()
    start_time = now - duration_seconds
    end_time = now

    db_session_factory = ctx.get("db_session_factory")
    redis = ctx.get("redis")
    media_path = Path(ctx.get("media_path") or constants.DEFAULT_MEDIA_PATH)

    recorders: dict[int, RingBufferRecorder] = ctx.get("recorders", {})
    recorder = recorders.get(streamer_id)

    if recorder:
        segments = recorder.get_segment_range(start_time, end_time)
    else:
        buffer_dir = media_path / constants.RING_BUFFER_DIR / str(streamer_id)
        segments = _find_segments_on_disk(buffer_dir, streamer_id, start_time, end_time)

    if not segments:
        return {"status": "error", "error": "No recent segments available for manual clip"}

    # Create Moment record in DB
    moment_id = None
    if db_session_factory:
        from app.models import Moment, StreamSession  # type: ignore
        from sqlalchemy import select  # type: ignore

        async with db_session_factory() as session:
            # Find active session if any
            stmt = select(StreamSession).where(
                StreamSession.streamer_id == streamer_id,
                StreamSession.status == "live",
            ).order_by(StreamSession.started_at.desc())
            res = await session.execute(stmt)
            active_session = res.scalars().first()
            session_id = active_session.id if active_session else None

            moment = Moment(
                session_id=session_id,
                streamer_id=streamer_id,
                hype_score=100.0,
                clip_start_time=start_time,
                clip_end_time=end_time,
                clip_duration=float(duration_seconds),
                status="clipping",
                trigger_type="manual",
            )
            session.add(moment)
            await session.commit()
            await session.refresh(moment)
            moment_id = moment.id

    clip_dir = media_path / constants.CLIPS_DIR
    clip_dir.mkdir(parents=True, exist_ok=True)
    out_file = clip_dir / f"manual_{streamer_id}_{int(start_time)}.mp4"

    try:
        clip_result = await cut_clip(
            segments=segments,
            start_time=start_time,
            end_time=end_time,
            output_path=out_file,
            thumbnail_time=now - 5.0,
        )

        if db_session_factory and moment_id:
            from app.models import Moment  # type: ignore
            async with db_session_factory() as session:
                moment = await session.get(Moment, moment_id)
                if moment:
                    moment.file_path = str(clip_result.file_path)
                    moment.thumbnail_path = (
                        str(clip_result.thumbnail_path) if clip_result.thumbnail_path else None
                    )
                    moment.clip_duration = clip_result.duration
                    moment.status = "clipped"
                    await session.commit()

        await _publish_event(redis, "moment_clipped", {
            "moment_id": moment_id,
            "streamer_id": streamer_id,
            "file_path": str(clip_result.file_path),
            "thumbnail_path": str(clip_result.thumbnail_path) if clip_result.thumbnail_path else None,
            "duration": clip_result.duration,
            "file_size": clip_result.file_size,
        })

        return {
            "status": "clipped",
            "moment_id": moment_id,
            "file_path": str(clip_result.file_path),
            "duration": clip_result.duration,
        }
    except Exception as e:
        logger.error("Error in manual_clip for streamer %d: %s", streamer_id, e)
        return {"status": "error", "error": str(e)}
