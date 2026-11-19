"""Hype detection task: reads platform chat, runs HypeDetector, and triggers moments."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from clipdeck.shared import constants
from clipdeck.shared.detection.audio_analyzer import AudioAnalyzer
from clipdeck.shared.detection.hype_detector import HypeDetector
from clipdeck.shared.detection.signals import DetectorConfig
from clipdeck.shared.platforms.base import ChatMessage, ChatReader, Platform
from clipdeck.shared.platforms.kick.chat import KickChatReader
from clipdeck.shared.platforms.twitch.chat import TwitchChatReader
from clipdeck.shared.platforms.youtube.chat import YouTubeChatReader

logger = logging.getLogger(__name__)


def _create_chat_reader(
    platform: str,
    channel: str,
    twitch_token: str | None = None,
    youtube_api_key: str | None = None,
) -> ChatReader:
    p = platform.lower()
    if p == "twitch":
        return TwitchChatReader(channel=channel, token=twitch_token)
    elif p == "kick":
        return KickChatReader(channel=channel)
    elif p == "youtube":
        if not youtube_api_key:
            raise ValueError("YouTube API key required for YouTube chat monitoring")
        return YouTubeChatReader(channel=channel, api_key=youtube_api_key)
    else:
        raise ValueError(f"Unsupported platform: {platform}")


async def _publish_event(redis: Any, event_type: str, data: dict[str, Any]) -> None:
    """Publish real-time event to Redis for API SSE broadcasting."""
    if redis is None:
        return
    try:
        payload = json.dumps({"event": event_type, "data": data})
        await redis.publish("clipdeck_events", payload)
    except Exception as e:
        logger.debug("Failed to publish event to Redis: %s", e)


async def run_detector(
    ctx: dict[str, Any],
    streamer_id: int,
    channel: str,
    platform: str,
    session_id: int,
    config_dict: dict | None = None,
    youtube_api_key: str | None = None,
    twitch_token: str | None = None,
) -> None:
    """Long-running task: monitors chat & audio for a live stream to detect hype."""
    logger.info(
        "Starting run_detector for streamer %d (%s on %s), session %d",
        streamer_id, channel, platform, session_id,
    )

    # Initialize configuration & detector
    detector_config = DetectorConfig()
    if config_dict:
        if "hype_threshold" in config_dict:
            detector_config.hype_threshold = float(config_dict["hype_threshold"])
        if "cooldown_secs" in config_dict:
            detector_config.cooldown_secs = float(config_dict["cooldown_secs"])
        if "clip_pre_secs" in config_dict:
            detector_config.clip_pre_secs = float(config_dict["clip_pre_secs"])
        if "clip_post_secs" in config_dict:
            detector_config.clip_post_secs = float(config_dict["clip_post_secs"])

    detector = HypeDetector(streamer_id=streamer_id, config=detector_config)
    audio_analyzer = AudioAnalyzer()
    chat_reader = _create_chat_reader(
        platform=platform,
        channel=channel,
        twitch_token=twitch_token,
        youtube_api_key=youtube_api_key,
    )

    msg_buffer: deque[ChatMessage] = deque()
    stop_event = asyncio.Event()
    ctx.setdefault("detector_stops", {})[streamer_id] = stop_event

    redis = ctx.get("redis")
    db_session_factory = ctx.get("db_session_factory")

    async def _message_consumer() -> None:
        """Background coroutine collecting messages from the chat reader."""
        try:
            async for msg in chat_reader.messages():
                msg_buffer.append(msg)
                if stop_event.is_set():
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Chat reader consumer exception for streamer %d: %s", streamer_id, e)

    consumer_task: asyncio.Task | None = None
    last_analyzed_segment: Path | None = None
    last_stats_persist_time: float = 0.0

    try:
        async with chat_reader:
            consumer_task = asyncio.create_task(_message_consumer())

            while not stop_event.is_set():
                now = time.time()

                # Drain current second messages
                batch: list[ChatMessage] = []
                while msg_buffer:
                    batch.append(msg_buffer.popleft())

                detector.feed_messages(batch, now)

                # Optional Audio Analysis
                recorders = ctx.get("recorders", {})
                recorder = recorders.get(streamer_id)
                if recorder and recorder.buffer_dir.exists():
                    recent_segs = sorted(
                        recorder.buffer_dir.glob(f"{streamer_id}_*.ts"),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                    if recent_segs:
                        newest_seg = recent_segs[0]
                        if newest_seg != last_analyzed_segment and (now - newest_seg.stat().st_mtime) < 6.0:
                            last_analyzed_segment = newest_seg
                            metrics = await audio_analyzer.analyze_segment_async(newest_seg)
                            if metrics.rms_db > -90.0:
                                detector.feed_audio(metrics.rms_db, now)

                # Query current score & check moments
                score_info = detector.get_current_score()

                # Check triggered moment
                if score_info.triggered_moment:
                    moment = score_info.triggered_moment
                    logger.info(
                        "Triggered moment for streamer %d! Peak=%.1f, Window=[%.1f, %.1f]",
                        streamer_id, moment.peak_score, moment.start_time, moment.end_time,
                    )
                    moment_id = None

                    # Persist Moment in DB if available
                    if db_session_factory:
                        try:
                            from app.models import Moment  # type: ignore
                            async with db_session_factory() as session:
                                new_moment = Moment(
                                    session_id=session_id,
                                    streamer_id=streamer_id,
                                    hype_score=moment.peak_score,
                                    clip_start_time=moment.start_time,
                                    clip_end_time=moment.end_time,
                                    clip_duration=moment.end_time - moment.start_time,
                                    chat_data={"signals": moment.signals_at_peak},
                                    chat_messages_snapshot={"messages": moment.top_messages},
                                    status="detected",
                                    trigger_type="auto",
                                )
                                session.add(new_moment)
                                await session.commit()
                                await session.refresh(new_moment)
                                moment_id = new_moment.id
                        except Exception as e:
                            logger.error("Failed to save detected moment to DB: %s", e)

                    # Notify SSE and enqueue clip task
                    await _publish_event(redis, "new_moment", {
                        "moment_id": moment_id,
                        "streamer_id": streamer_id,
                        "session_id": session_id,
                        "peak_score": moment.peak_score,
                        "start_time": moment.start_time,
                        "end_time": moment.end_time,
                    })

                    # If ARQ redis pool available, enqueue clip_moment job
                    arq_redis = ctx.get("arq_redis")
                    if arq_redis and moment_id:
                        await arq_redis.enqueue_job("clip_moment", moment_id=moment_id)

                # Persist stats bucket & broadcast live score every 5 seconds
                if now - last_stats_persist_time >= 5.0:
                    last_stats_persist_time = now
                    stats = detector.get_stats_bucket()
                    if stats and db_session_factory:
                        try:
                            from app.models import ChatStatsBucket  # type: ignore
                            async with db_session_factory() as session:
                                bucket = ChatStatsBucket(
                                    session_id=session_id,
                                    timestamp=datetime.utcfromtimestamp(stats.timestamp),
                                    messages_per_second=stats.messages_per_second,
                                    hype_score=stats.hype_score,
                                    top_emotes=stats.top_emotes,
                                    signals=stats.signals,
                                    caps_ratio=stats.caps_ratio,
                                    copypasta_ratio=stats.copypasta_ratio,
                                )
                                session.add(bucket)
                                await session.commit()
                        except Exception as e:
                            logger.debug("Failed to persist stats bucket: %s", e)

                    # Broadcast SSE hype update
                    await _publish_event(redis, "hype_update", {
                        "streamer_id": streamer_id,
                        "session_id": session_id,
                        "score": score_info.score,
                        "signals": score_info.signals,
                        "timestamp": now,
                    })

                await asyncio.sleep(1.0)

    except asyncio.CancelledError:
        logger.info("Detector task for streamer %d cancelled", streamer_id)
    finally:
        stop_event.set()
        if consumer_task and not consumer_task.done():
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass
        ctx.get("detector_stops", {}).pop(streamer_id, None)
        logger.info("Detector task for streamer %d finished", streamer_id)
