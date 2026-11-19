"""Local faster-whisper transcription engine with word timestamps."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from clipdeck.shared.transcription.base import (
    Transcriber,
    TranscriptResult,
    TranscriptSegment,
    WordTimestamp,
)

logger = logging.getLogger(__name__)


class WhisperLocalTranscriber(Transcriber):
    """Local faster-whisper transcription provider."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel  # type: ignore
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            except ImportError:
                logger.warning(
                    "faster_whisper is not installed. WhisperLocalTranscriber will run in mock mode."
                )
                self._model = "MOCK"
        return self._model

    async def transcribe(self, media_path: Path) -> TranscriptResult:
        """Run local whisper transcription in an executor to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, media_path)

    def _transcribe_sync(self, media_path: Path) -> TranscriptResult:
        model = self._get_model()

        if model == "MOCK":
            return self._mock_transcript(media_path)

        # Extract audio to 16kHz WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)

        try:
            # Synchronous audio extraction
            import subprocess
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-loglevel",
                "warning",
                "-y",
                "-i",
                str(media_path),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(wav_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True)

            segments_iter, info = model.transcribe(
                str(wav_path),
                word_timestamps=True,
                vad_filter=True,
            )

            all_segments: list[TranscriptSegment] = []
            all_words: list[WordTimestamp] = []
            full_text_parts: list[str] = []

            for seg_idx, s in enumerate(segments_iter):
                seg_words: list[WordTimestamp] = []
                if hasattr(s, "words") and s.words:
                    for w in s.words:
                        wt = WordTimestamp(
                            word=w.word.strip(),
                            start=round(float(w.start), 3),
                            end=round(float(w.end), 3),
                            confidence=round(float(getattr(w, "probability", 1.0)), 3),
                        )
                        seg_words.append(wt)
                        all_words.append(wt)

                seg_obj = TranscriptSegment(
                    id=seg_idx,
                    start=round(float(s.start), 3),
                    end=round(float(s.end), 3),
                    text=s.text.strip(),
                    words=seg_words,
                )
                all_segments.append(seg_obj)
                full_text_parts.append(s.text.strip())

            return TranscriptResult(
                text=" ".join(full_text_parts),
                segments=all_segments,
                words=all_words,
                language=info.language if hasattr(info, "language") else "en",
                duration=info.duration if hasattr(info, "duration") else 0.0,
            )
        finally:
            if wav_path.exists():
                wav_path.unlink()

    def _mock_transcript(self, media_path: Path) -> TranscriptResult:
        """Fallback mock transcript for testing when faster-whisper is unavailable."""
        words_sample = [
            ("Yo", 0.0, 0.4),
            ("chat", 0.4, 0.8),
            ("look", 0.8, 1.1),
            ("at", 1.1, 1.3),
            ("this", 1.3, 1.6),
            ("play", 1.6, 2.0),
            ("oh", 2.2, 2.5),
            ("my", 2.5, 2.7),
            ("god", 2.7, 3.1),
            ("we", 3.2, 3.4),
            ("won", 3.4, 3.8),
            ("that", 3.8, 4.1),
        ]
        words = [WordTimestamp(w, s, e, 0.95) for w, s, e in words_sample]
        seg1 = TranscriptSegment(0, 0.0, 2.0, "Yo chat look at this play", words[:6])
        seg2 = TranscriptSegment(1, 2.2, 4.1, "oh my god we won that", words[6:])
        return TranscriptResult(
            text="Yo chat look at this play oh my god we won that",
            segments=[seg1, seg2],
            words=words,
            language="en",
            duration=4.5,
        )
