"""Blurred background 9:16 layout builder."""

from __future__ import annotations


def build_blurred_bg_filter(
    input_label: str = "0:v",
    output_label: str = "layout_out",
    blur_radius: int = 25,
) -> str:
    """
    Generate an FFmpeg filtergraph string placing 16:9 video centered
    over a blurred, cropped 1080x1920 background.
    """
    return (
        f"[{input_label}]split=2[bg_in][fg_in];"
        f"[bg_in]scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,boxblur={blur_radius}:5[bg];"
        f"[fg_in]scale=1080:608:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[{output_label}]"
    )
