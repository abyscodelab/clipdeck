"""Stacked Facecam + Gameplay 9:16 layout builder."""

from __future__ import annotations

from clipdeck.shared.ai.edl_schema import CropBox


def build_facecam_split_filter(
    input_label: str = "0:v",
    output_label: str = "layout_out",
    facecam_crop: CropBox | None = None,
    gameplay_crop: CropBox | None = None,
    top_height: int = 720,
    bottom_height: int = 1200,
) -> str:
    """
    Generate an FFmpeg filtergraph stacking facecam on top (1080x720)
    and gameplay on bottom (1080x1200) into a single 1080x1920 canvas.
    """
    # If crop coords provided, use them; otherwise default to top-left for facecam
    if facecam_crop and facecam_crop.width > 0:
        fc_crop_expr = f"crop=iw*{facecam_crop.width}:ih*{facecam_crop.height}:iw*{facecam_crop.x}:ih*{facecam_crop.y},"
    else:
        # Default top-left webcam crop (e.g. 25% width, 30% height)
        fc_crop_expr = "crop=iw*0.28:ih*0.35:0:0,"

    if gameplay_crop and gameplay_crop.width > 0:
        gp_crop_expr = f"crop=iw*{gameplay_crop.width}:ih*{gameplay_crop.height}:iw*{gameplay_crop.x}:ih*{gameplay_crop.y},"
    else:
        # Full screen center crop
        gp_crop_expr = ""

    return (
        f"[{input_label}]split=2[cam_in][game_in];"
        f"[cam_in]{fc_crop_expr}scale=1080:{top_height}:force_original_aspect_ratio=increase,crop=1080:{top_height}[cam_out];"
        f"[game_in]{gp_crop_expr}scale=1080:{bottom_height}:force_original_aspect_ratio=increase,crop=1080:{bottom_height}[game_out];"
        f"[cam_out][game_out]vstack=inputs=2[{output_label}]"
    )
