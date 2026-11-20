"""Subtle-powered subtitle generator with animated word highlights and smart grouping."""

from __future__ import annotations

import logging
from pathlib import Path
from clipdeck.shared.ai.edl_schema import CaptionStyle
from clipdeck.shared.transcription.base import WordTimestamp

logger = logging.getLogger(__name__)


def generate_ass_subtitles(
    words: list[WordTimestamp],
    output_path: Path,
    style: CaptionStyle | None = None,
    words_per_group: int = 4,
    time_offset: float = 0.0,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """
    Generate an ASS subtitle file using the Subtle caption styling engine.
    Applies Subtle's typography, colors, position, and word-by-word active pop highlights.
    
    Parameters
    ----------
    words:
        List of words with word-level timestamps.
    output_path:
        Path where .ass file should be written.
    style:
        CaptionStyle specifying Subtle style name and parameters.
    words_per_group:
        Default fallback chunking if group data unavailable.
    time_offset:
        Offset in seconds subtracted if the clip was trimmed.
    width, height:
        Video frame dimensions (default 1080x1920 vertical).
    """
    from clipdeck.shared.render.subtle_engine import SubtleEngine

    caption_style = style or CaptionStyle()
    engine = SubtleEngine()

    # Create temporary words.json and captions.json for subtle grouping if possible
    words_json = output_path.with_suffix(".tmp_words.json")
    captions_json = output_path.with_suffix(".tmp_captions.json")

    try:
        engine.prepare_words_json(
            words=words,
            output_file=words_json,
            time_offset=time_offset,
            duration_sec=30.0,
            width=width,
            height=height,
        )

        # Run Subtle group.py synchronously via helper if available
        import subprocess
        clean_style = (caption_style.style or "glide").split(":")[0]
        style_file = engine.styles_dir / f"{clean_style}.json"
        if not style_file.exists():
            style_file = engine.styles_dir / "glide.json"

        cmd = [
            engine.python_bin,
            str(engine.scripts_dir / "group.py"),
            str(words_json),
            "--style",
            str(style_file),
            "--out",
            str(captions_json),
            "--emphasis",
            caption_style.emphasis,
            "--numbers",
            caption_style.numbers,
        ]
        if caption_style.emphasis_words:
            cmd.extend(["--emphasis-words", caption_style.emphasis_words])

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            logger.debug("Subtle group.py direct run notice: %s", r.stderr[:200])
    except Exception as e:
        logger.debug("Subtle group sync run fallback: %s", e)

    # Generate ASS file using SubtleEngine styling
    engine.generate_subtle_ass(
        captions_json_path=captions_json,
        words=words,
        output_path=output_path,
        style_name=caption_style.style or "glide",
        time_offset=time_offset,
        c_style=caption_style,
        width=width,
        height=height,
    )

    # Clean up temp files
    words_json.unlink(missing_ok=True)
    captions_json.unlink(missing_ok=True)

    return output_path
