"""OpenAI Whisper API transcription provider."""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from pathlib import Path

import aiohttp

from clipdeck.shared.transcription.base import (
    Transcriber,
    TranscriptResult,
    TranscriptSegment,
    WordTimestamp,
)

logger = logging.getLogger(__name__)

OPENAI_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"


class WhisperAPITranscriber(Transcriber):
    """Transcribes audio using OpenAI's Whisper Cloud API."""

    def __init__(self, api_key: str, model: str = "whisper-1") -> None:
        self.api_key = api_key
        self.model = model

    async def transcribe(self, media_path: Path) -> TranscriptResult:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)

        try:
            await self.extract_audio_wav(media_path, wav_path)

            data = aiohttp.FormData()
            data.add_field("model", self.model)
            data.add_field("response_format", "verbose_json")
            data.add_field("timestamp_granularities[]", "word")
            data.add_field("timestamp_granularities[]", "segment")

            with open(wav_path, "rb") as f:
                data.add_field("file", f.read(), filename="audio.wav", content_type="audio/wav")

            headers = {"Authorization": f"Bearer {self.api_key}"}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    OPENAI_TRANSCRIPTION_URL,
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error("OpenAI Whisper API error (%d): %s", resp.status, err_text)
                        raise RuntimeError(f"OpenAI Whisper API failed: {err_text}")
                    result_json = await resp.json()

            all_words: list[WordTimestamp] = []
            for w in result_json.get("words", []):
                all_words.append(
                    WordTimestamp(
                        word=w.get("word", "").strip(),
                        start=round(float(w.get("start", 0.0)), 3),
                        end=round(float(w.get("end", 0.0)), 3),
                        confidence=1.0,
                    )
                )

            all_segments: list[TranscriptSegment] = []
            for s in result_json.get("segments", []):
                s_start = round(float(s.get("start", 0.0)), 3)
                s_end = round(float(s.get("end", 0.0)), 3)
                s_words = [w for w in all_words if s_start <= w.start <= s_end]
                all_segments.append(
                    TranscriptSegment(
                        id=int(s.get("id", len(all_segments))),
                        start=s_start,
                        end=s_end,
                        text=s.get("text", "").strip(),
                        words=s_words,
                    )
                )

            return TranscriptResult(
                text=result_json.get("text", "").strip(),
                segments=all_segments,
                words=all_words,
                language=result_json.get("language", "en"),
                duration=float(result_json.get("duration", 0.0)),
            )

        finally:
            if wav_path.exists():
                wav_path.unlink()
