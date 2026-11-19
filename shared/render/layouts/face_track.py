"""Face-tracking / center vertical crop layout builder."""

from __future__ import annotations


def build_face_track_filter(
    input_label: str = "0:v",
    output_label: str = "layout_out",
    pan_x: float = 0.5,
) -> str:
    """
    Generate an FFmpeg filtergraph cropping 9:16 vertical slice centered on pan_x (0.0=left, 1.0=right)
    and scaling to 1080x1920.
    """
    # 9:16 aspect ratio relative to input height
    # crop_w = ih * 9/16, crop_x = (iw - crop_w) * pan_x
    return (
        f"[{input_label}]crop=w='ih*(9/16)':h='ih':x='(iw-ow)*{pan_x}':y=0,"
        f"scale=1080:1920[{output_label}]"
    )
