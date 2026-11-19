"""Full automated AI editing pipeline: Transcribe -> Score -> EDL -> Render."""

from __future__ import annotations

import json
import logging
from typing import Any

from clipdeck.worker.tasks.edit import generate_edl_task
from clipdeck.worker.tasks.render import render_clip_task
from clipdeck.worker.tasks.score import score_moment_task
from clipdeck.worker.tasks.transcribe import transcribe_moment

logger = logging.getLogger(__name__)


async def _publish_event(redis: Any, event_type: str, data: dict[str, Any]) -> None:
    if redis is None:
        return
    try:
        payload = json.dumps({"event": event_type, "data": data})
        await redis.publish("clipdeck_events", payload)
    except Exception as e:
        logger.debug("Failed to publish event to Redis: %s", e)


async def process_moment_pipeline(
    ctx: dict[str, Any],
    moment_id: int,
    ai_model: str = "gemini-1.5-flash",
    layout_type: str = "blurred_bg",
    transcribe_provider: str = "whisper_local",
    job_id: int | None = None,
) -> dict[str, Any]:
    """Execute the end-to-end AI editing pipeline for a moment."""
    logger.info("Starting process_moment_pipeline for moment_id=%d", moment_id)
    redis = ctx.get("redis")
    db_session_factory = ctx.get("db_session_factory")

    async def _update_job(progress: float, log_line: str, status: str = "running"):
        await _publish_event(redis, "pipeline_progress", {
            "moment_id": moment_id,
            "job_id": job_id,
            "progress": progress,
            "message": log_line,
        })
        if db_session_factory and job_id:
            from app.models import Job  # type: ignore
            try:
                async with db_session_factory() as session:
                    j = await session.get(Job, job_id)
                    if j:
                        j.progress = progress
                        j.status = status
                        j.log = (j.log or "") + f"\n[{progress:.0f}%] {log_line}"
                        await session.commit()
            except Exception as err:
                logger.debug("Failed to update job record: %s", err)

    # 1. Transcribe audio
    await _update_job(15.0, "Transcribing spoken audio with word timestamps...")
    t_res = await transcribe_moment(
        ctx=ctx,
        moment_id=moment_id,
        provider=transcribe_provider,
    )
    if t_res.get("status") == "error":
        err = t_res.get("error", "Unknown transcription error")
        await _update_job(100.0, f"Transcription error: {err}", status="failed")
        return {"status": "error", "step": "transcribe", "error": err}

    # 2. Score moment for virality & playbook rules
    await _update_job(40.0, "Evaluating moment virality with LLM & playbooks...")
    s_res = await score_moment_task(
        ctx=ctx,
        moment_id=moment_id,
        provider_name="gemini" if "gemini" in ai_model else "openai",
        model=ai_model,
    )
    if s_res.get("status") == "error":
        err = s_res.get("error", "Unknown scoring error")
        await _update_job(100.0, f"Scoring error: {err}", status="failed")
        return {"status": "error", "step": "score", "error": err}

    if not s_res.get("keep", False):
        await _update_job(
            100.0,
            f"Moment rejected by editor: {s_res.get('rule_violations') or 'Low virality potential'}",
            status="completed",
        )
        return {"status": "rejected", "score_result": s_res}

    # 3. Generate EDL
    await _update_job(65.0, "Generating Edit Decision List (EDL) and titles...")
    e_res = await generate_edl_task(
        ctx=ctx,
        moment_id=moment_id,
        provider_name="gemini" if "gemini" in ai_model else "openai",
        model=ai_model,
        layout_type=layout_type,
    )
    if e_res.get("status") == "error":
        err = e_res.get("error", "Unknown EDL error")
        await _update_job(100.0, f"EDL error: {err}", status="failed")
        return {"status": "error", "step": "edl", "error": err}

    clip_id = e_res.get("clip_id")

    # 4. Render vertical 9:16 short
    await _update_job(80.0, "Rendering 9:16 vertical short with FFmpeg...")
    r_res = await render_clip_task(ctx=ctx, clip_id=clip_id)
    if r_res.get("status") == "error":
        err = r_res.get("error", "Unknown rendering error")
        await _update_job(100.0, f"Rendering error: {err}", status="failed")
        return {"status": "error", "step": "render", "error": err}

    await _update_job(100.0, "Video rendering complete! Clip ready for preview.", status="completed")

    return {
        "status": "completed",
        "moment_id": moment_id,
        "clip_id": clip_id,
        "file_path": r_res.get("file_path"),
        "duration": r_res.get("duration"),
    }
