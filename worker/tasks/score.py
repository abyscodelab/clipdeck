"""Score task: Evaluates moment virality and rule compliance using LLMs."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from sqlalchemy import select

from clipdeck.shared.ai.base import AIProvider
from clipdeck.shared.ai.playbook_engine import Playbook
from clipdeck.shared.ai.providers.anthropic import AnthropicProvider
from clipdeck.shared.ai.providers.gemini import GeminiProvider
from clipdeck.shared.ai.providers.openai import OpenAIProvider
from clipdeck.shared.ai.providers.openrouter import OpenRouterProvider
from clipdeck.shared.ai.scoring import score_moment
from clipdeck.shared.transcription.base import TranscriptResult, TranscriptSegment, WordTimestamp

logger = logging.getLogger(__name__)


def _resolve_ai_provider(provider_name: str, model: str | None = None) -> AIProvider:
    p = provider_name.lower()
    if "anthropic" in p or "claude" in p:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        return AnthropicProvider(api_key=key, model=model or "claude-3-5-sonnet-20241022")
    elif "gemini" in p or "google" in p:
        key = os.getenv("GEMINI_API_KEY", "")
        return GeminiProvider(api_key=key, model=model or "gemini-1.5-flash")
    elif "openrouter" in p:
        key = os.getenv("OPENROUTER_API_KEY", "")
        return OpenRouterProvider(api_key=key, model=model or "anthropic/claude-3.5-sonnet")
    else:
        key = os.getenv("OPENAI_API_KEY", "")
        return OpenAIProvider(api_key=key, model=model or "gpt-4o-mini")


async def _publish_event(redis: Any, event_type: str, data: dict[str, Any]) -> None:
    if redis is None:
        return
    try:
        payload = json.dumps({"event": event_type, "data": data})
        await redis.publish("clipdeck_events", payload)
    except Exception as e:
        logger.debug("Failed to publish event to Redis: %s", e)


async def score_moment_task(
    ctx: dict[str, Any],
    moment_id: int,
    provider_name: str = "gemini",
    model: str | None = None,
) -> dict[str, Any]:
    """Score a moment for virality and playbook rule adherence."""
    logger.info("Starting score_moment_task for moment_id=%d", moment_id)
    db_session_factory = ctx.get("db_session_factory")
    redis = ctx.get("redis")

    if not db_session_factory:
        return {"status": "error", "error": "db_session_factory missing"}

    from app.models import Moment, Playbook as DBPlaybook, Streamer  # type: ignore

    async with db_session_factory() as session:
        moment = await session.get(Moment, moment_id)
        if not moment:
            return {"status": "error", "error": f"Moment {moment_id} not found"}

        streamer = await session.get(Streamer, moment.streamer_id)
        streamer_name = streamer.name if streamer else "streamer"

        # Fetch active playbooks
        pb_stmt = select(DBPlaybook).where(DBPlaybook.enabled.is_(True))
        pb_res = await session.execute(pb_stmt)
        db_playbooks = list(pb_res.scalars().all())

        engine_playbooks = [
            Playbook(
                id=str(p.id),
                name=p.name,
                level=p.scope,
                content_markdown=p.content,
            )
            for p in db_playbooks
        ]

        chat_data = moment.chat_data or {}
        transcript_raw = chat_data.get("transcript")
        if transcript_raw:
            transcript = TranscriptResult(
                text=transcript_raw.get("text", ""),
                language=transcript_raw.get("language", "en"),
                duration=float(transcript_raw.get("duration", 0.0)),
                words=[WordTimestamp(**w) for w in transcript_raw.get("words", [])],
                segments=[
                    TranscriptSegment(
                        id=s["id"],
                        start=s["start"],
                        end=s["end"],
                        text=s["text"],
                        words=[WordTimestamp(**w) for w in s.get("words", [])],
                    )
                    for s in transcript_raw.get("segments", [])
                ],
            )
        else:
            transcript = TranscriptResult(text="", segments=[], words=[])

        chat_snapshot = moment.chat_messages_snapshot or {}
        chat_messages = chat_snapshot.get("messages", [])
        hype_metrics = {
            "peak_score": moment.hype_score,
            "chat_velocity_zscore": chat_data.get("signals", {}).get("chat_velocity_zscore", 0.0),
            "emote_density": chat_data.get("signals", {}).get("emote_density", 0.0),
        }

    ai_provider = _resolve_ai_provider(provider_name, model)
    score_res = await score_moment(
        ai_provider=ai_provider,
        transcript=transcript,
        chat_messages=chat_messages,
        hype_metrics=hype_metrics,
        streamer_name=streamer_name,
        playbooks=engine_playbooks,
    )

    async with db_session_factory() as session:
        moment = await session.get(Moment, moment_id)
        if moment:
            cdata = dict(moment.chat_data or {})
            cdata["score_result"] = score_res.model_dump()
            moment.chat_data = cdata
            if not score_res.keep:
                moment.status = "rejected"
            await session.commit()

    await _publish_event(redis, "moment_scored", {
        "moment_id": moment_id,
        "keep": score_res.keep,
        "virality_score": score_res.virality_score,
        "category": score_res.category,
        "reason": score_res.reason,
        "rule_violations": score_res.rule_violations,
    })

    return {
        "status": "completed",
        "moment_id": moment_id,
        "keep": score_res.keep,
        "virality_score": score_res.virality_score,
        "category": score_res.category,
        "rule_violations": score_res.rule_violations,
    }
