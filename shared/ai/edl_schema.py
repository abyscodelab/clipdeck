"""Strict Pydantic schemas for Edit Decision Lists (EDL) and Moment Scoring."""

from __future__ import annotations

from typing import Any, Literal
try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:  # type: ignore
        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

        def model_dump(self) -> dict[str, Any]:
            res: dict[str, Any] = {}
            for k, v in self.__dict__.items():
                if hasattr(v, "model_dump"):
                    res[k] = v.model_dump()
                elif isinstance(v, list):
                    res[k] = [item.model_dump() if hasattr(item, "model_dump") else item for item in v]
                elif isinstance(v, dict):
                    res[k] = {
                        dk: dv.model_dump() if hasattr(dv, "model_dump") else dv
                        for dk, dv in v.items()
                    }
                else:
                    res[k] = v
            return res

        def model_copy(self, update: dict[str, Any] | None = None) -> "BaseModel":
            d = dict(self.__dict__)
            if update:
                d.update(update)
            return type(self)(**d)

    def Field(default: Any = ..., default_factory: Any = None, **kwargs: Any) -> Any:  # type: ignore
        if default_factory is not None:
            return default_factory()
        return default



# ---------------------------------------------------------------------------
# Moment Scoring Schema
# ---------------------------------------------------------------------------

class MomentScoreResult(BaseModel):
    """Evaluation of a moment's virality and suitability for clipping."""

    keep: bool = Field(..., description="Whether this moment should be clipped and published.")
    virality_score: float = Field(
        ..., ge=0.0, le=100.0, description="Predicted virality potential from 0 to 100."
    )
    reason: str = Field(..., description="Brief editorial justification for the score.")
    category: str = Field(
        ...,
        description="Virality archetype: clutch, funny, rage, wholesome, hot_take, chat_wild, or reaction.",
    )
    best_in: float = Field(..., description="Suggested optimal in-point timestamp in seconds.")
    best_out: float = Field(..., description="Suggested optimal out-point timestamp in seconds.")
    playbook_rules_applied: list[str] = Field(
        default_factory=list, description="List of playbook rule IDs or descriptions applied."
    )
    rule_violations: list[str] = Field(
        default_factory=list, description="Hard or soft rule violations identified, if any."
    )


# ---------------------------------------------------------------------------
# Edit Decision List (EDL) Schema
# ---------------------------------------------------------------------------

class Trim(BaseModel):
    """Start and end bounds relative to original clip or segment."""

    in_point: float = Field(..., ge=0.0, description="Start time offset in seconds.")
    out_point: float = Field(..., gt=0.0, description="End time offset in seconds.")


class CutSegment(BaseModel):
    """Dead air or boring pauses to cut out within the trimmed range."""

    start: float = Field(..., ge=0.0, description="Start offset in seconds of the segment to cut.")
    end: float = Field(..., gt=0.0, description="End offset in seconds of the segment to cut.")
    reason: str = Field("dead air > 0.7s", description="Why this portion is cut.")


class CropBox(BaseModel):
    """Bounding box for cropping (normalized 0.0-1.0 or pixel coordinates)."""

    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0


class LayoutConfig(BaseModel):
    """Target layout configuration for vertical 9:16 canvas."""

    type: Literal["blurred_bg", "facecam_split", "face_track"] = Field(
        "blurred_bg",
        description="Layout type: blurred_bg (fit over blur), facecam_split (stacked), or face_track (center pan).",
    )
    facecam_crop: CropBox | None = Field(
        None, description="Crop box for webcam area in facecam_split mode."
    )
    gameplay_crop: CropBox | None = Field(
        None, description="Crop box for game/screen area in facecam_split mode."
    )


class ZoomPunch(BaseModel):
    """Punch-in zoom effect applied at a climax timestamp."""

    timestamp: float = Field(..., ge=0.0, description="Offset timestamp in seconds.")
    scale: float = Field(1.15, ge=1.05, le=1.5, description="Zoom scale factor (e.g. 1.15).")
    duration: float = Field(1.0, ge=0.2, le=3.0, description="Duration of zoom punch in seconds.")


class CaptionStyle(BaseModel):
    """Subtle animated captions styling parameters (https://github.com/0xpratzyy/subtle)."""

    style: str = "glide"  # Any subtle style: glide, punch, terminal, glass, whisper, keyword, impact, bottom, cards, etc.
    variant: str = ""  # Optional variant (e.g. "yellow", "lit", "marker")
    emphasis: str = "auto"  # auto, numbers, off
    emphasis_words: str = ""  # words to highlight for sure
    numbers: str = "auto"  # auto, western, indian, off
    behind: str = "auto"  # auto, on, off
    placement: str = "auto"  # auto, off
    cuts: str = "auto"  # auto, off
    palette: str = "auto"  # auto, off
    legibility: str = "auto"  # auto, off
    position: Literal["bottom", "middle", "top"] = "bottom"
    font: str = "Montserrat ExtraBold"
    font_size: int = 48
    primary_color: str = "&H00FFFFFF"  # White in ASS hex
    highlight_color: str = "&H0000FFFF"  # Yellow in ASS hex
    outline_color: str = "&H00000000"  # Black outline


class PlatformMetadata(BaseModel):
    """Platform-specific titles, captions, and tags."""

    title: str = Field(..., max_length=100)
    description: str = Field(..., max_length=2200)
    hashtags: list[str] = Field(default_factory=list)


class EditDecisionList(BaseModel):
    """Complete machine-executable recipe for editing a moment into a vertical short."""

    trim: Trim
    cuts: list[CutSegment] = Field(default_factory=list)
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    hook_text: str | None = Field(None, description="Punchy text overlay for first 2-3s.")
    hook_duration: float = Field(2.5, ge=1.0, le=4.0)
    captions: CaptionStyle = Field(default_factory=CaptionStyle)
    zoom_punches: list[ZoomPunch] = Field(default_factory=list)
    title: str = Field(..., description="High-performing main video title.")
    description: str = Field(..., description="Caption/description with streamer credit.")
    hashtags: list[str] = Field(default_factory=list)
    per_platform: dict[str, PlatformMetadata] = Field(default_factory=dict)
