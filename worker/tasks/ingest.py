"""Ingest tasks: start and stop stream ring-buffer recording."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from clipdeck.shared import constants
from clipdeck.shared.media.ring_buffer import RecorderConfig, RingBufferRecorder

logger = logging.getLogger(__name__)


async def start_recording(
    ctx: dict[str, Any],
    streamer_id: int,
    stream_url: str,
    media_path: str | None = None,
) -> dict[str, Any]:
    """Start recording a stream into the local ring buffer."""
    recorders: dict[int, RingBufferRecorder] = ctx.setdefault("recorders", {})

    if streamer_id in recorders and recorders[streamer_id].is_alive():
        logger.info("Recorder already running for streamer %d", streamer_id)
        return {"status": "already_running", "streamer_id": streamer_id}

    storage_root = Path(media_path) if media_path else constants.DEFAULT_MEDIA_PATH
    config = RecorderConfig(media_dir=storage_root)

    recorder = RingBufferRecorder(
        streamer_id=streamer_id,
        stream_url=stream_url,
        config=config,
    )

    try:
        await recorder.start()
        recorders[streamer_id] = recorder
        logger.info("Successfully started recorder for streamer %d", streamer_id)
        return {"status": "started", "streamer_id": streamer_id, "stream_url": stream_url}
    except Exception as e:
        logger.error("Failed to start recorder for streamer %d: %s", streamer_id, e)
        return {"status": "error", "error": str(e), "streamer_id": streamer_id}


async def stop_recording(
    ctx: dict[str, Any],
    streamer_id: int,
) -> dict[str, Any]:
    """Stop recording a stream and free subprocesses."""
    recorders: dict[int, RingBufferRecorder] = ctx.setdefault("recorders", {})

    recorder = recorders.pop(streamer_id, None)
    if recorder:
        try:
            await recorder.stop()
            logger.info("Stopped recorder for streamer %d", streamer_id)
            return {"status": "stopped", "streamer_id": streamer_id}
        except Exception as e:
            logger.error("Error stopping recorder for streamer %d: %s", streamer_id, e)
            return {"status": "error", "error": str(e), "streamer_id": streamer_id}

    return {"status": "not_running", "streamer_id": streamer_id}
