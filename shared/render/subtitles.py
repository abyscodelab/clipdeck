"""ASS (Advanced SubStation Alpha) subtitle generator with animated word highlights."""

from __future__ import annotations

import logging
from pathlib import Path
from clipdeck.shared.ai.edl_schema import CaptionStyle
from clipdeck.shared.transcription.base import WordTimestamp

logger = logging.getLogger(__name__)


def _format_ass_time(seconds: float) -> str:
    """Format seconds into ASS timestamp H:MM:SS.cs."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        secs += 1
        centis = 0
    return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"


def generate_ass_subtitles(
    words: list[WordTimestamp],
    output_path: Path,
    style: CaptionStyle | None = None,
    words_per_group: int = 4,
    time_offset: float = 0.0,
) -> Path:
    """
    Generate an ASS subtitle file with animated word pop/highlighting for 1080x1920 vertical video.
    
    Parameters
    ----------
    words:
        List of words with word-level timestamps.
    output_path:
        Path where .ass file should be written.
    style:
        CaptionStyle specifying colors and font size.
    words_per_group:
        Number of words displayed simultaneously on screen (default 4).
    time_offset:
        Offset in seconds subtracted if the clip was trimmed.
    """
    caption_style = style or CaptionStyle()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Vertical position in 1080x1920 canvas
    margin_v = 420  # bottom third safe zone above UI
    if caption_style.position == "middle":
        margin_v = 900
    elif caption_style.position == "top":
        margin_v = 1500

    ass_header = f"""[Script Info]
Title: ClipDeck Auto-Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{caption_style.font},{caption_style.font_size},{caption_style.primary_color},&H000000FF,{caption_style.outline_color},&H80000000,-1,0,0,0,100,100,1,0,1,6,2,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: list[str] = []

    # Adjust words by time_offset
    adjusted_words = [
        WordTimestamp(
            word=w.word.strip(),
            start=max(0.0, w.start - time_offset),
            end=max(0.0, w.end - time_offset),
            confidence=w.confidence,
        )
        for w in words
        if (w.end - time_offset) >= 0.0
    ]

    # Chunk words into small groups (e.g. 3-4 words per card)
    for i in range(0, len(adjusted_words), words_per_group):
        group = adjusted_words[i : i + words_per_group]
        if not group:
            continue

        # For each word in the group, create a dialogue event highlighting that specific word
        for active_idx, active_word in enumerate(group):
            w_start = _format_ass_time(active_word.start)
            w_end = _format_ass_time(active_word.end)

            line_parts = []
            for j, w in enumerate(group):
                clean_word = w.word.upper()
                if j == active_idx:
                    # Active word: pop scale 115% and highlight color
                    line_parts.append(
                        f"{{\\c{caption_style.highlight_color}&\\fscx115\\fscy115}}{clean_word}{{\\r}}"
                    )
                else:
                    # Normal word: white color
                    line_parts.append(f"{{\\c{caption_style.primary_color}&}}{clean_word}")

            formatted_text = " ".join(line_parts)
            events.append(f"Dialogue: 0,{w_start},{w_end},Default,,0,0,0,,{formatted_text}")

    content = ass_header + "\n".join(events) + "\n"
    output_path.write_text(content, encoding="utf-8")
    return output_path
