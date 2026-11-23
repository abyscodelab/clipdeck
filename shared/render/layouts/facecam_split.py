"""Stacked Facecam + Gameplay 9:16 vertical layout builder.

Implements the viral gaming Shorts format:
- Top 45-50% (1080x900): Facecam closely cropped to reaction expressions
- Bottom 50-55% (1080x1020): Gameplay action cropped and centered
- Seam Divider / Center Hook zone: Y: 875 - 1005
"""

from __future__ import annotations

from typing import Any


def build_facecam_split_filter(
    input_label: str = "0:v",
    output_label: str = "layout_out",
    facecam_crop: Any | None = None,
    gameplay_crop: Any | None = None,
    top_height: int = 900,
    bottom_height: int = 1020,
    add_divider: bool = True,
) -> str:
    """
    Generate an FFmpeg filtergraph stacking facecam on top (1080x900)
    and gameplay on bottom (1080x1020) into a single 1080x1920 canvas.
    """
    # If crop coords provided (as CropBox or dict), use them; otherwise default to bottom-left webcam (Speed/Kai style)
    if facecam_crop is not None:
        if hasattr(facecam_crop, "width") and facecam_crop.width > 0:
            fc_crop_expr = f"crop=iw*{facecam_crop.width}:ih*{facecam_crop.height}:iw*{facecam_crop.x}:ih*{facecam_crop.y},"
        elif isinstance(facecam_crop, dict) and facecam_crop.get("width", 0) > 0:
            fc_crop_expr = f"crop=iw*{facecam_crop['width']}:ih*{facecam_crop['height']}:iw*{facecam_crop['x']}:ih*{facecam_crop['y']},"
        else:
            fc_crop_expr = "crop=iw*0.35:ih*0.48:0:ih*0.52,"
    else:
        # Default: Speed/Kai bottom-left webcam crop
        fc_crop_expr = "crop=iw*0.35:ih*0.48:0:ih*0.52,"

    if gameplay_crop is not None:
        if hasattr(gameplay_crop, "width") and gameplay_crop.width > 0:
            gp_crop_expr = f"crop=iw*{gameplay_crop.width}:ih*{gameplay_crop.height}:iw*{gameplay_crop.x}:ih*{gameplay_crop.y},"
        elif isinstance(gameplay_crop, dict) and gameplay_crop.get("width", 0) > 0:
            gp_crop_expr = f"crop=iw*{gameplay_crop['width']}:ih*{gameplay_crop['height']}:iw*{gameplay_crop['x']}:ih*{gameplay_crop['y']},"
        else:
            # Default gameplay: center-right 75% width
            gp_crop_expr = "crop=iw*0.75:ih:iw*0.25:0,"
    else:
        # Default gameplay: center 75% width
        gp_crop_expr = "crop=iw*0.75:ih:iw*0.25:0,"

    stack_label = "stacked" if add_divider else output_label
    filter_chain = (
        f"[{input_label}]split=2[cam_in][game_in];"
        f"[cam_in]{fc_crop_expr}scale=1080:{top_height}:force_original_aspect_ratio=increase,crop=1080:{top_height}[cam_out];"
        f"[game_in]{gp_crop_expr}scale=1080:{bottom_height}:force_original_aspect_ratio=increase,crop=1080:{bottom_height}[game_out];"
        f"[cam_out][game_out]vstack=inputs=2[{stack_label}]"
    )

    if add_divider:
        seam_y = top_height - 2
        filter_chain += f";[{stack_label}]drawbox=y={seam_y}:w=1080:h=4:color=white@0.3:t=fill[{output_label}]"

    return filter_chain
