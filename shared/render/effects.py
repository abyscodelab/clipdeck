"""Visual effects: Hook text overlays and climax zoom punches."""

from __future__ import annotations

import re
from clipdeck.shared.ai.edl_schema import ZoomPunch


_has_drawtext: bool | None = None


def has_drawtext_filter() -> bool:
    """Check if the system FFmpeg binary has drawtext filter enabled."""
    global _has_drawtext
    if _has_drawtext is not None:
        return _has_drawtext
    try:
        import subprocess
        res = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True, timeout=2)
        _has_drawtext = "drawtext" in res.stdout
    except Exception:
        _has_drawtext = False
    return _has_drawtext


def _escape_drawtext(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\\\''")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    return text


def build_hook_text_filter(
    hook_text: str,
    duration: float = 2.5,
    input_label: str = "hook_in",
    output_label: str = "hook_out",
) -> str:
    """
    Build drawtext filter displaying bold hook text at top of screen for duration seconds.
    If drawtext filter is not supported by FFmpeg binary, safely passes through.
    """
    if not has_drawtext_filter():
        return f"[{input_label}]null[{output_label}]"

    escaped = _escape_drawtext(hook_text.strip().upper())
    return (
        f"[{input_label}]drawtext=text='{escaped}':"
        f"fontsize=54:fontcolor=white:"
        f"box=1:boxcolor=black@0.75:boxborderw=20:"
        f"x=(w-text_w)/2:y=280:"
        f"enable='between(t,0,{duration:.2f})'[{output_label}]"
    )


def build_zoom_punch_filter(
    punches: list[ZoomPunch],
    input_label: str = "zoom_in",
    output_label: str = "zoom_out",
) -> str:
    """
    Build zoom punch crop/scale expressions for climax moments.
    """
    if not punches:
        return f"[{input_label}]null[{output_label}]"

    # Support the primary zoom punch
    p = punches[0]
    t_start = p.timestamp
    t_end = p.timestamp + p.duration
    scale = p.scale

    # Zoom in by cropping centered area and scaling back to 1080x1920
    # ow = 1080 / scale, oh = 1920 / scale
    crop_w = int(1080 / scale)
    crop_h = int(1920 / scale)
    crop_x = int((1080 - crop_w) / 2)
    crop_y = int((1920 - crop_h) / 2)

    return (
        f"[{input_label}]split=2[z_norm][z_punch];"
        f"[z_punch]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale=1080:1920[z_punched];"
        f"[z_norm][z_punched]overlay=0:0:enable='between(t,{t_start:.2f},{t_end:.2f})'[{output_label}]"
    )
