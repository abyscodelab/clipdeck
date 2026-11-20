"""End-to-end verification test for Subtle Captions integration in ClipDeck."""

import asyncio
import logging
from pathlib import Path

from clipdeck.shared.ai.edl_schema import CaptionStyle, EditDecisionList, LayoutConfig, Trim
from clipdeck.shared.render.renderer import VerticalVideoRenderer
from clipdeck.shared.render.subtle_engine import SubtleEngine
from clipdeck.shared.transcription.base import WordTimestamp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_subtle")


async def main():
    engine = SubtleEngine()
    styles = engine.list_styles()
    logger.info("Found %d Subtle styles: %s...", len(styles), [s["name"] for s in styles[:8]])
    assert len(styles) >= 35, f"Expected at least 35 styles, got {len(styles)}"

    # Check key styles exist
    style_names = {s["name"] for s in styles}
    for expected in ["glide", "punch", "terminal", "glass", "keyword", "impact", "bottom", "cards"]:
        assert expected in style_names, f"Expected style '{expected}' missing from styles"
    logger.info("Subtle style catalog verified.")

    # Prepare test inputs
    test_video = Path(__file__).resolve().parent / "test_clip.mp4"
    assert test_video.exists(), f"Missing test clip: {test_video}"

    words = [
        WordTimestamp(word="ClipDeck", start=0.5, end=1.2, confidence=0.99),
        WordTimestamp(word="captions", start=1.25, end=1.8, confidence=0.98),
        WordTimestamp(word="powered", start=1.85, end=2.3, confidence=0.97),
        WordTimestamp(word="by", start=2.35, end=2.6, confidence=0.99),
        WordTimestamp(word="Subtle", start=2.65, end=3.4, confidence=0.99),
        WordTimestamp(word="are", start=3.5, end=3.8, confidence=0.95),
        WordTimestamp(word="insanely", start=3.85, end=4.4, confidence=0.98),
        WordTimestamp(word="clean", start=4.45, end=5.2, confidence=0.99),
        WordTimestamp(word="and", start=5.3, end=5.5, confidence=0.95),
        WordTimestamp(word="viral!", start=5.55, end=6.8, confidence=0.99),
    ]

    edl = EditDecisionList(
        trim=Trim(in_point=0.0, out_point=7.0),
        layout=LayoutConfig(type="blurred_bg"),
        hook_text="SUBTLE CAPTIONS",
        hook_duration=2.0,
        captions=CaptionStyle(
            style="punch",
            emphasis="auto",
            numbers="auto",
        ),
        title="Subtle Captions Demo",
        description="Rendered with Subtle engine",
    )

    out_video = Path(__file__).resolve().parent / "test_rendered_subtle_punch.mp4"
    if out_video.exists():
        out_video.unlink()

    renderer = VerticalVideoRenderer(fps=30)
    logger.info("Executing VerticalVideoRenderer with Subtle 'punch' style...")
    result = await renderer.render(
        input_video_path=test_video,
        edl=edl,
        words=words,
        output_path=out_video,
    )

    logger.info(
        "Render finished: file=%s (size=%d bytes, duration=%.1fs, thumb=%s)",
        result.file_path,
        result.file_size,
        result.duration,
        result.thumbnail_path,
    )

    assert result.file_path.exists(), "Output video file does not exist"
    assert result.file_size > 50_000, f"Output video file too small: {result.file_size} bytes"
    assert result.duration > 0.0, "Output video duration invalid"

    # Verify sidecar captions and srt
    captions_file = out_video.with_name(f"{out_video.stem}.captions.json")
    srt_file = out_video.with_suffix(".srt")
    assert captions_file.exists(), "captions.json not generated"
    assert srt_file.exists(), "srt file not generated"

    logger.info("ALL SUBTLE INTEGRATION TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
