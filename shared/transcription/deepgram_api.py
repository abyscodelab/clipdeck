"""Deepgram Nova-2 API transcription provider with word-level timestamps."""

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

DEEPGRAM_LISTEN_URL = (
    "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&punctuate=true&utterances=true"
)


class DeepgramTranscriber(Transcriber):
    """Transcribes audio using Deepgram's high-speed Nova-2 API."""

    def __init__(self, api_key: str, model: str = "nova-2") -> None:
        self.api_key = api_key
        self.model = model

    async def transcribe(self, media_path: Path) -> TranscriptResult:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)

        try:
            await self.extract_audio_wav(media_path, wav_path)

            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "audio/wav",
            }
            url = f"https://api.deepgram.com/v1/listen?model={self.model}&smart_format=true&punctuate=true&utterances=true"

            with open(wav_path, "rb") as f:
                audio_bytes = f.read()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    data=audio_bytes,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error("Deepgram API error (%d): %s", resp.status, err_text)
                        raise RuntimeError(f"Deepgram API failed: {err_text}")
                    data = await resp.json()

            results = data.get("results", {})
            channels = results.get("channels", [])
            if not channels:
                return TranscriptResult(text="", segments=[], words=[])

            alt = channels[0].get("alternatives", [{}])[0]
            transcript_text = alt.get("transcript", "").strip()

            all_words: list[WordTimestamp] = []
            for w in alt.get("words", []):
                all_words.append(
                    WordTimestamp(
                        word=w.get("punctuated_word", w.get("word", "")).strip(),
                        start=round(float(w.get("start", 0.0)), 3),
                        end=round(float(w.get("end", 0.0)), 3),
                        confidence=round(float(w.get("confidence", 1.0)), 3),
                    )
                )

            all_segments: list[TranscriptSegment] = []
            utterances = results.get("utterances", [])
            if utterances:
                for idx, u in enumerate(utterances):
                    u_start = round(float(u.get("start", 0.0)), 3)
                    u_end = round(float(u.get("end", 0.0)), 3)
                    u_words = [w for w in all_words if u_start <= w.start <= u_end]
                    all_segments.append(
                        TranscriptSegment(
                            id=idx,
                            start=u_start,
                            end=u_end,
                            text=u.get("transcript", "").strip(),
                            words=u_words,
                        )
                    )
            else:
                # Group words into sentence-like segments of ~10 words
                chunk_size = 10
                for i in range(0, len(all_words), chunk_size):
                    chunk = all_words[i : i + chunk_size]
                    if chunk:
                        all_segments.append(
                            TranscriptSegment(
                                id=len(all_segments),
                                start=chunk[0].start,
                                end=chunk[-1].end,
                                text=" ".join(w.word for w in chunk),
                                words=chunk,
                            )
                        )

            duration = 0.0
            if all_words:
                duration = all_words[-1].end

            return TranscriptResult(
                text=transcript_text,
                segments=all_segments,
                words=all_words,
                language="en",
                duration=duration,
            )

        finally:
            if wav_path.exists():
                wav_path.unlink()
