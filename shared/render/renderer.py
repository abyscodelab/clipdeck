"""Deterministic 9:16 vertical video rendering engine."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from clipdeck.shared.ai.edl_schema import EditDecisionList
from clipdeck.shared.media.ffmpeg_utils import build_thumbnail_command, probe_media_file
from clipdeck.shared.render.effects import build_hook_text_filter, build_zoom_punch_filter
from clipdeck.shared.render.layouts.blurred_bg import build_blurred_bg_filter
from clipdeck.shared.render.layouts.face_track import build_face_track_filter
from clipdeck.shared.render.layouts.facecam_split import build_facecam_split_filter
from clipdeck.shared.render.subtle_engine import SubtleEngine
from clipdeck.shared.transcription.base import WordTimestamp

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RenderResult:
    """Result of a vertical video rendering job."""

    file_path: Path
    thumbnail_path: Path | None
    duration: float
    file_size: int


class VerticalVideoRenderer:
    """Renders 1080x1920 vertical shorts from landscape footage using an EDL."""

    def __init__(self, fps: int = 30) -> None:
        self.fps = fps

    async def render(
        self,
        input_video_path: Path,
        edl: EditDecisionList,
        words: list[WordTimestamp] | None = None,
        output_path: Path | None = None,
    ) -> RenderResult:
        """
        Execute deterministic FFmpeg pipeline:
        1. Trim input to [in_point, out_point]
        2. Apply 9:16 layout (blurred_bg / facecam_split / face_track)
        3. Apply zoom punch if configured
        4. Apply hook text overlay in first 2.5s
        5. Burn ASS animated karaoke subtitles
        6. Apply -14 LUFS audio loudness normalization
        7. Encode H.264 + AAC with +faststart
        """
        if not input_video_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_video_path}")

        if output_path is None:
            output_path = input_video_path.with_name(f"{input_video_path.stem}_9x16.mp4")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        thumb_path = output_path.with_suffix(".jpg")

        in_point = edl.trim.in_point
        out_point = edl.trim.out_point
        duration = max(1.0, out_point - in_point)

        # Base intermediate video if captions will be applied by Subtle
        has_captions = bool(words)
        base_video_path = output_path.with_name(f"{output_path.stem}_base.mp4") if has_captions else output_path

        try:
            # 1. Build layout filter
            layout_type = edl.layout.type
            if layout_type == "facecam_split":
                layout_filter = build_facecam_split_filter(
                    input_label="0:v",
                    output_label="v_layout",
                    facecam_crop=edl.layout.facecam_crop,
                    gameplay_crop=edl.layout.gameplay_crop,
                )
            elif layout_type == "face_track":
                layout_filter = build_face_track_filter(
                    input_label="0:v",
                    output_label="v_layout",
                )
            else:
                layout_filter = build_blurred_bg_filter(
                    input_label="0:v",
                    output_label="v_layout",
                )

            # 2. Build zoom punches filter
            # Adjust punch timestamps relative to trim in_point
            adjusted_punches = [
                p.model_copy(update={"timestamp": max(0.0, p.timestamp - in_point)})
                for p in edl.zoom_punches
                if in_point <= p.timestamp <= out_point
            ]
            zoom_filter = build_zoom_punch_filter(
                punches=adjusted_punches,
                input_label="v_layout",
                output_label="v_zoom",
            )

            # 3. Build hook text filter
            if edl.hook_text:
                hook_filter = build_hook_text_filter(
                    hook_text=edl.hook_text,
                    duration=edl.hook_duration,
                    input_label="v_zoom",
                    output_label="v_hook",
                )
                final_v_label = "v_hook"
            else:
                hook_filter = "[v_zoom]null[v_hook]"
                final_v_label = "v_hook"

            # Assemble full video filtergraph for base 9:16 layout
            filter_complex = f"{layout_filter};{zoom_filter};{hook_filter}"

            # Audio filter: -14 LUFS broadcast normalization
            audio_filter = "loudnorm=I=-14:TP=-1.5:LRA=11"

            # FFmpeg CLI command to render base 9:16 short
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-loglevel",
                "warning",
                "-y",
                "-ss",
                f"{in_point:.3f}",
                "-to",
                f"{out_point:.3f}",
                "-i",
                str(input_video_path),
                "-filter_complex",
                filter_complex,
                "-map",
                f"[{final_v_label}]",
                "-map",
                "0:a?",
                "-af",
                audio_filter,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-r",
                str(self.fps),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-movflags",
                "+faststart",
                str(base_video_path),
            ]

            logger.info("Starting vertical base render: %s", " ".join(cmd[:12]))
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace")
                logger.error("FFmpeg render failed (%d): %s", proc.returncode, err_msg)
                raise RuntimeError(f"FFmpeg render failed: {err_msg}")

            # 4. Apply Subtle Captions
            if has_captions and words:
                logger.info("Applying Subtle captions (style: %s)...", edl.captions.style)
                subtle_engine = SubtleEngine()
                await subtle_engine.render(
                    video_path=base_video_path,
                    words=words,
                    caption_style=edl.captions,
                    output_path=output_path,
                    time_offset=in_point,
                )
                if base_video_path.exists() and base_video_path != output_path:
                    base_video_path.unlink()

            # Generate 1080x1920 vertical GTA VI-style thumbnail
            try:
                from clipdeck.shared.media.gta_vertical_thumbnail import (
                    build_vertical_thumbnail,
                    extract_hook_words,
                )
                raw_snap = output_path.with_name(f"{output_path.stem}_raw_snap.jpg")
                thumb_cmd = build_thumbnail_command(
                    video_path=output_path,
                    output_thumb_path=raw_snap,
                    timestamp_secs=min(2.5, duration / 2.0),
                )
                thumb_proc = await asyncio.create_subprocess_exec(
                    *thumb_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await thumb_proc.wait()

                title_source = edl.title or edl.hook_text or "INSANE MOMENT"
                w1, w2 = extract_hook_words(title_source)
                build_vertical_thumbnail(
                    out_path=thumb_path,
                    word1=w1,
                    word2=w2,
                    hero_image=raw_snap if raw_snap.exists() else None,
                    mode="cinematic",
                    badge_title="GTA VI",
                    badge_sub="CLIPPED",
                )
                if raw_snap.exists():
                    raw_snap.unlink()
            except Exception as e:
                logger.warning("GTA vertical thumbnail generation fallback: %s", e)
                thumb_cmd = build_thumbnail_command(
                    video_path=output_path,
                    output_thumb_path=thumb_path,
                    timestamp_secs=duration / 2.0,
                )
                thumb_proc = await asyncio.create_subprocess_exec(
                    *thumb_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await thumb_proc.wait()

            # Probe duration & size
            probe = await probe_media_file(output_path)
            actual_duration = duration
            if "format" in probe and "duration" in probe["format"]:
                try:
                    actual_duration = float(probe["format"]["duration"])
                except Exception:
                    pass

            file_size = output_path.stat().st_size if output_path.exists() else 0

            return RenderResult(
                file_path=output_path,
                thumbnail_path=thumb_path if thumb_path.exists() else None,
                duration=round(actual_duration, 2),
                file_size=file_size,
            )

        finally:
            if base_video_path.exists() and base_video_path != output_path:
                try:
                    base_video_path.unlink()
                except OSError:
                    pass
