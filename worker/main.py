"""ClipDeck Worker Entry Point.

Runs the ARQ background worker and the live stream polling service.
Responsible for orchestrating recorders, chat readers, hype detectors,
and clip renderers.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from arq import create_pool
    from arq.connections import RedisSettings
except ImportError:
    create_pool = None  # type: ignore

    class RedisSettings:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        @classmethod
        def from_dsn(cls, dsn: str) -> "RedisSettings":
            return cls()

try:
    from redis import asyncio as aioredis
except ImportError:
    aioredis = None  # type: ignore

try:
    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
except ImportError:
    select = update = None  # type: ignore
    AsyncSession = async_sessionmaker = create_async_engine = None  # type: ignore


# Ensure both clipdeck and api modules can be imported
BASE_DIR = Path(__file__).resolve().parent.parent
API_DIR = BASE_DIR / "api"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from clipdeck.shared import constants
from clipdeck.shared.platforms.base import LiveChecker, Platform, StreamInfo
from clipdeck.shared.platforms.kick.api import KickAPI
from clipdeck.shared.platforms.twitch.api import TwitchHelixAPI
from clipdeck.shared.platforms.youtube.api import YouTubeAPI
from clipdeck.worker.tasks.clip import clip_moment, manual_clip
from clipdeck.worker.tasks.detect import run_detector
from clipdeck.worker.tasks.edit import generate_edl_task
from clipdeck.worker.tasks.ingest import start_recording, stop_recording
from clipdeck.worker.tasks.pipeline import process_moment_pipeline
from clipdeck.worker.tasks.render import render_clip_task
from clipdeck.worker.tasks.score import score_moment_task
from clipdeck.worker.tasks.transcribe import transcribe_moment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("clipdeck.worker")

# Configuration from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./clipdeck.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MEDIA_STORAGE_PATH = Path(os.getenv("MEDIA_STORAGE_PATH", "./media"))
POLL_INTERVAL_SECS = int(os.getenv("LIVE_POLL_INTERVAL_SECS", str(constants.LIVE_POLL_INTERVAL_SECS)))


# ---------------------------------------------------------------------------
# High-Level Monitoring Operations
# ---------------------------------------------------------------------------

async def start_monitoring(ctx: dict[str, Any], streamer_id: int) -> dict[str, Any]:
    """Start full monitoring (recording + detection) for a live streamer."""
    logger.info("start_monitoring called for streamer_id=%d", streamer_id)
    db_session_factory = ctx.get("db_session_factory")
    if not db_session_factory:
        return {"status": "error", "error": "db_session_factory missing"}

    from app.models import Streamer, StreamSession  # type: ignore

    async with db_session_factory() as session:
        streamer = await session.get(Streamer, streamer_id)
        if not streamer:
            return {"status": "error", "error": f"Streamer {streamer_id} not found"}

        # Find or create active StreamSession
        stmt = select(StreamSession).where(
            StreamSession.streamer_id == streamer_id,
            StreamSession.status == "live",
        ).order_by(StreamSession.started_at.desc())
        res = await session.execute(stmt)
        stream_session = res.scalars().first()

        if not stream_session:
            stream_session = StreamSession(
                streamer_id=streamer_id,
                status="live",
                started_at=datetime.utcnow(),
            )
            session.add(stream_session)
            await session.commit()
            await session.refresh(stream_session)

        session_id = stream_session.id
        platform = streamer.platform
        name = streamer.name
        stream_url = streamer.url or (
            f"https://twitch.tv/{name}" if platform == "twitch" else
            f"https://kick.com/{name}" if platform == "kick" else ""
        )
        config_dict = streamer.config or {}

    # Start ring buffer recorder
    media_path = str(ctx.get("media_path", MEDIA_STORAGE_PATH))
    await start_recording(ctx, streamer_id=streamer_id, stream_url=stream_url, media_path=media_path)

    # Spawn detector task in background
    detector_tasks: dict[int, asyncio.Task] = ctx.setdefault("detector_tasks", {})
    if streamer_id not in detector_tasks or detector_tasks[streamer_id].done():
        task = asyncio.create_task(
            run_detector(
                ctx=ctx,
                streamer_id=streamer_id,
                channel=name,
                platform=platform,
                session_id=session_id,
                config_dict=config_dict,
            )
        )
        detector_tasks[streamer_id] = task

    return {"status": "monitoring_started", "streamer_id": streamer_id, "session_id": session_id}


async def stop_monitoring(ctx: dict[str, Any], streamer_id: int) -> dict[str, Any]:
    """Stop recording and detection for a streamer."""
    logger.info("stop_monitoring called for streamer_id=%d", streamer_id)

    # Stop detector
    detector_stops: dict[int, asyncio.Event] = ctx.get("detector_stops", {})
    if streamer_id in detector_stops:
        detector_stops[streamer_id].set()

    detector_tasks: dict[int, asyncio.Task] = ctx.get("detector_tasks", {})
    task = detector_tasks.pop(streamer_id, None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Stop recording
    await stop_recording(ctx, streamer_id=streamer_id)

    # End stream session in DB
    db_session_factory = ctx.get("db_session_factory")
    if db_session_factory:
        from app.models import StreamSession  # type: ignore
        async with db_session_factory() as session:
            stmt = select(StreamSession).where(
                StreamSession.streamer_id == streamer_id,
                StreamSession.status == "live",
            )
            res = await session.execute(stmt)
            for sess in res.scalars():
                sess.status = "ended"
                sess.ended_at = datetime.utcnow()
            await session.commit()

    return {"status": "monitoring_stopped", "streamer_id": streamer_id}


# ---------------------------------------------------------------------------
# Background Live Poller Service
# ---------------------------------------------------------------------------

class LivePoller:
    """Periodically queries platform APIs for auto-monitored streamers."""

    def __init__(self, ctx: dict[str, Any], interval_secs: int = 60) -> None:
        self.ctx = ctx
        self.interval_secs = interval_secs
        self._running = False
        self._task: asyncio.Task | None = None
        self._active_streamers: set[int] = set()

        self.twitch_api = TwitchHelixAPI()
        self.kick_api = KickAPI()
        self.youtube_api = YouTubeAPI()

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("LivePoller started (interval=%ds)", self.interval_secs)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.twitch_api.close()
        await self.kick_api.close()
        await self.youtube_api.close()
        logger.info("LivePoller stopped")

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in LivePoller cycle: %s", e)

            await asyncio.sleep(self.interval_secs)

    async def poll_once(self) -> None:
        db_session_factory = self.ctx.get("db_session_factory")
        if not db_session_factory:
            return

        from app.models import Streamer  # type: ignore

        # 1. Fetch all auto-monitored streamers
        async with db_session_factory() as session:
            stmt = select(Streamer).where(Streamer.auto_monitor.is_(True))
            res = await session.execute(stmt)
            streamers = list(res.scalars().all())

        if not streamers:
            return

        # Group by platform
        twitch_streamers = [s for s in streamers if s.platform == "twitch"]
        kick_streamers = [s for s in streamers if s.platform == "kick"]
        yt_streamers = [s for s in streamers if s.platform == "youtube"]

        live_streamer_ids: set[int] = set()

        # Check Twitch batch
        if twitch_streamers:
            names = [s.name for s in twitch_streamers]
            infos = await self.twitch_api.batch_check(names)
            live_names = {info.channel_name.lower() for info in infos if info.is_live}
            for s in twitch_streamers:
                if s.name.lower() in live_names:
                    live_streamer_ids.add(s.id)

        # Check Kick batch
        if kick_streamers:
            infos = await self.kick_api.batch_check([s.name for s in kick_streamers])
            live_names = {info.channel_name.lower() for info in infos if info.is_live}
            for s in kick_streamers:
                if s.name.lower() in live_names:
                    live_streamer_ids.add(s.id)

        # Check YouTube
        if yt_streamers:
            infos = await self.youtube_api.batch_check([s.platform_id or s.name for s in yt_streamers])
            live_ids = {info.channel_id for info in infos if info.is_live}
            for s in yt_streamers:
                if (s.platform_id or s.name) in live_ids:
                    live_streamer_ids.add(s.id)

        # Detect transitions
        # Streamers that just went live:
        went_live = live_streamer_ids - self._active_streamers
        for sid in went_live:
            logger.info("Streamer %d WENT LIVE. Starting monitoring...", sid)
            await start_monitoring(self.ctx, sid)

        # Streamers that went offline:
        went_offline = self._active_streamers - live_streamer_ids
        for sid in went_offline:
            logger.info("Streamer %d WENT OFFLINE. Stopping monitoring...", sid)
            await stop_monitoring(self.ctx, sid)

        self._active_streamers = live_streamer_ids


# ---------------------------------------------------------------------------
# ARQ Worker Lifecycle Hooks
# ---------------------------------------------------------------------------

async def startup(ctx: dict[str, Any]) -> None:
    """Initialize DB, Redis, and background services on ARQ worker boot."""
    logger.info("Initializing ClipDeck ARQ worker...")

    db_url = DATABASE_URL
    if db_url.startswith("sqlite://"):
        db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    engine = create_async_engine(
        db_url,
        connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    redis = aioredis.from_url(REDIS_URL, decode_responses=False)
    arq_redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))

    ctx["db_engine"] = engine
    ctx["db_session_factory"] = session_factory
    ctx["redis"] = redis
    ctx["arq_redis"] = arq_redis
    ctx["media_path"] = MEDIA_STORAGE_PATH
    ctx["recorders"] = {}
    ctx["detector_tasks"] = {}
    ctx["detector_stops"] = {}

    # Start live poller
    poller = LivePoller(ctx=ctx, interval_secs=POLL_INTERVAL_SECS)
    await poller.start()
    ctx["poller"] = poller

    logger.info("Worker startup completed successfully")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Clean up active processes and connections on worker shutdown."""
    logger.info("Shutting down ClipDeck ARQ worker...")

    # Stop live poller
    poller = ctx.get("poller")
    if poller:
        await poller.stop()

    # Stop active detectors
    detector_stops = ctx.get("detector_stops", {})
    for stop_ev in detector_stops.values():
        stop_ev.set()

    detector_tasks = ctx.get("detector_tasks", {})
    for task in detector_tasks.values():
        if not task.done():
            task.cancel()

    # Stop all ring buffer recorders
    recorders = ctx.get("recorders", {})
    for rec in list(recorders.values()):
        await rec.stop()

    # Close Redis & DB
    redis = ctx.get("redis")
    if redis:
        await redis.close()

    arq_redis = ctx.get("arq_redis")
    if arq_redis:
        await arq_redis.close()

    db_engine = ctx.get("db_engine")
    if db_engine:
        await db_engine.dispose()

    logger.info("Worker shutdown clean")


# ---------------------------------------------------------------------------
# ARQ Worker Settings
# ---------------------------------------------------------------------------

class WorkerSettings:
    """Settings class read by ARQ worker runner."""

    functions = [
        start_monitoring,
        stop_monitoring,
        start_recording,
        stop_recording,
        run_detector,
        clip_moment,
        manual_clip,
        transcribe_moment,
        score_moment_task,
        generate_edl_task,
        render_clip_task,
        process_moment_pipeline,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 20
    poll_delay = 0.5


if __name__ == "__main__":
    import arq
    arq.run_worker(WorkerSettings)
