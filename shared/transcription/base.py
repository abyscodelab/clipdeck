"""Abstract base classes and data structures for audio transcription."""

from __future__ import annotations

import abc
import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WordTimestamp:
    """Precise start and end timestamp for an individual spoken word."""

    word: str
    start: float
    end: float
    confidence: float = 1.0


@dataclass(slots=True)
class TranscriptSegment:
    """A sentence or clause-level segment with start/end bounds."""

    id: int
    start: float
    end: float
    text: str
    words: list[WordTimestamp] = field(default_factory=list)


@dataclass(slots=True)
class TranscriptResult:
    """Full transcription result for an audio/video file."""

    text: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    words: list[WordTimestamp] = field(default_factory=list)
    language: str = "en"
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "duration": self.duration,
            "segments": [
                {
                    "id": s.id,
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "words": [
                        {
                            "word": w.word,
                            "start": w.start,
                            "end": w.end,
                            "confidence": w.confidence,
                        }
                        for w in s.words
                    ],
                }
                for s in self.segments
            ],
            "words": [
                {
                    "word": w.word,
                    "start": w.start,
                    "end": w.end,
                    "confidence": w.confidence,
                }
                for w in self.words
            ],
        }


class Transcriber(abc.ABC):
    """Abstract base class for audio transcription providers."""

    @abc.abstractmethod
    async def transcribe(self, media_path: Path) -> TranscriptResult:
        """Transcribe an audio or video file, returning word-level timestamps."""
        pass

    @staticmethod
    async def extract_audio_wav(
        media_path: Path,
        output_wav: Path,
        sample_rate: int = 16000,
    ) -> Path:
        """Extract a 16kHz mono WAV file from a video or audio file for transcription."""
        output_wav.parent.mkdir(parents=True, exist_ok=True)
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
            str(sample_rate),
            "-ac",
            "1",
            str(output_wav),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")
            logger.error("FFmpeg audio extraction failed: %s", err)
            raise RuntimeError(f"FFmpeg audio extraction failed: {err}")
        return output_wav
