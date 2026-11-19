"""Edit task: Generates structured EDL (Edit Decision List) for moments."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from clipdeck.shared.ai.edl_generator import generate_edl
from clipdeck.shared.ai.edl_schema import EditDecisionList, MomentScoreResult
from clipdeck.shared.ai.playbook_engine import Playbook
from clipdeck.shared.transcription.base import TranscriptResult, TranscriptSegment, WordTimestamp
from clipdeck.worker.tasks.score import _resolve_ai_provider

logger = logging.getLogger(__name__)


async def _publish_event(redis: Any, event_type: str, data: dict[str, Any]) -> None:
    if redis is None:
        return
    try:
        payload = json.dumps({"event": event_type, "data": data})
        await redis.publish("clipdeck_events", payload)
    except Exception as e:
        logger.debug("Failed to publish event to Redis: %s", e)


async def generate_edl_task(
    ctx: dict[str, Any],
    moment_id: int,
    provider_name: str = "gemini",
    model: str | None = None,
    layout_type: str = "blurred_bg",
) -> dict[str, Any]:
    """Generate EditDecisionList and record a Clip + EditVersion in DB."""
    logger.info("Starting generate_edl_task for moment_id=%d", moment_id)
    db_session_factory = ctx.get("db_session_factory")
    redis = ctx.get("redis")

    if not db_session_factory:
        return {"status": "error", "error": "db_session_factory missing"}

    from app.models import Clip, EditVersion, Moment, Playbook as DBPlaybook, Streamer  # type: ignore

    async with db_session_factory() as session:
        moment = await session.get(Moment, moment_id)
        if not moment:
            return {"status": "error", "error": f"Moment {moment_id} not found"}

        streamer = await session.get(Streamer, moment.streamer_id)
        streamer_name = streamer.name if streamer else "streamer"

        # Load active playbooks
        pb_stmt = select(DBPlaybook).where(DBPlaybook.enabled.is_(True))
        pb_res = await session.execute(pb_stmt)
        engine_playbooks = [
            Playbook(
                id=str(p.id),
                name=p.name,
                level=p.scope,
                content_markdown=p.content,
            )
            for p in pb_res.scalars().all()
        ]

        chat_data = moment.chat_data or {}
        score_dict = chat_data.get("score_result")
        if score_dict:
            score_res = MomentScoreResult(**score_dict)
        else:
            score_res = MomentScoreResult(
                keep=True,
                virality_score=moment.hype_score,
                reason="Automatic fallback score",
                category="chat_wild",
                best_in=0.0,
                best_out=moment.clip_duration or 30.0,
            )

        transcript_raw = chat_data.get("transcript") or {}
        transcript = TranscriptResult(
            text=transcript_raw.get("text", ""),
            duration=float(transcript_raw.get("duration", 0.0)),
            words=[WordTimestamp(**w) for w in transcript_raw.get("words", [])],
        )

        chat_messages = (moment.chat_messages_snapshot or {}).get("messages", [])

    ai_provider = _resolve_ai_provider(provider_name, model)
    edl: EditDecisionList = await generate_edl(
        ai_provider=ai_provider,
        score_result=score_res,
        transcript=transcript,
        chat_messages=chat_messages,
        streamer_name=streamer_name,
        playbooks=engine_playbooks,
        layout_type=layout_type,
    )

    clip_id = None
    async with db_session_factory() as session:
        # Check if Clip already exists for this moment
        stmt = select(Clip).where(Clip.moment_id == moment_id)
        res = await session.execute(stmt)
        clip = res.scalars().first()

        if not clip:
            clip = Clip(
                moment_id=moment_id,
                streamer_id=moment.streamer_id,
                title=edl.title,
                description=edl.description,
                hashtags=edl.hashtags,
                status="editing",
                aspect_ratio="9:16",
            )
            session.add(clip)
            await session.commit()
            await session.refresh(clip)
        else:
            clip.title = edl.title
            clip.description = edl.description
            clip.hashtags = edl.hashtags
            clip.status = "editing"
            await session.commit()

        clip_id = clip.id

        # Record EditVersion
        ver_stmt = select(EditVersion).where(EditVersion.clip_id == clip_id).order_by(EditVersion.version_number.desc())
        ver_res = await session.execute(ver_stmt)
        latest_ver = ver_res.scalars().first()
        next_ver_num = (latest_ver.version_number + 1) if latest_ver else 1

        edit_version = EditVersion(
            clip_id=clip_id,
            version_number=next_ver_num,
            edl_data=edl.model_dump(),
            ai_reasoning=score_res.reason,
            model_used=model or provider_name,
        )
        session.add(edit_version)
        await session.commit()

    await _publish_event(redis, "edl_generated", {
        "clip_id": clip_id,
        "moment_id": moment_id,
        "title": edl.title,
        "layout": edl.layout.type,
        "trim": edl.trim.model_dump(),
        "hook_text": edl.hook_text,
    })

    return {
        "status": "completed",
        "clip_id": clip_id,
        "moment_id": moment_id,
        "title": edl.title,
        "edl": edl.model_dump(),
    }
