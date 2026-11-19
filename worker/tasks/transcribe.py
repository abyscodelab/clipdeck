"""Transcription task: extracts audio and transcribes spoken dialogue with word timestamps."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from clipdeck.shared.transcription.base import TranscriptResult
from clipdeck.shared.transcription.factory import get_transcriber

logger = logging.getLogger(__name__)


async def _publish_event(redis: Any, event_type: str, data: dict[str, Any]) -> None:
    if redis is None:
        return
    try:
        payload = json.dumps({"event": event_type, "data": data})
        await redis.publish("clipdeck_events", payload)
    except Exception as e:
        logger.debug("Failed to publish event to Redis: %s", e)


async def transcribe_moment(
    ctx: dict[str, Any],
    moment_id: int,
    provider: str = "whisper_local",
    model: str | None = None,
) -> dict[str, Any]:
    """Transcribe audio for a moment."""
    logger.info("Starting transcribe_moment for moment_id=%d using %s", moment_id, provider)
    db_session_factory = ctx.get("db_session_factory")
    redis = ctx.get("redis")

    if not db_session_factory:
        return {"status": "error", "error": "db_session_factory missing"}

    from app.models import Moment  # type: ignore

    async with db_session_factory() as session:
        moment = await session.get(Moment, moment_id)
        if not moment:
            return {"status": "error", "error": f"Moment {moment_id} not found"}

        file_path_str = moment.file_path
        if not file_path_str or not Path(file_path_str).exists():
            return {"status": "error", "error": f"Clip file not found: {file_path_str}"}

        video_path = Path(file_path_str)

    try:
        transcriber = get_transcriber(provider=provider, model=model)
        result: TranscriptResult = await transcriber.transcribe(video_path)

        async with db_session_factory() as session:
            moment = await session.get(Moment, moment_id)
            if moment:
                chat_data = dict(moment.chat_data or {})
                chat_data["transcript"] = result.to_dict()
                moment.chat_data = chat_data
                await session.commit()

        await _publish_event(redis, "moment_transcribed", {
            "moment_id": moment_id,
            "text": result.text,
            "duration": result.duration,
            "word_count": len(result.words),
        })

        return {
            "status": "completed",
            "moment_id": moment_id,
            "text": result.text,
            "duration": result.duration,
            "words_count": len(result.words),
        }

    except Exception as e:
        logger.error("Failed to transcribe moment %d: %s", moment_id, e)
        return {"status": "error", "error": str(e)}
