"""Factory function for instantiating transcription providers."""

from __future__ import annotations

import os
from clipdeck.shared.transcription.base import Transcriber
from clipdeck.shared.transcription.deepgram_api import DeepgramTranscriber
from clipdeck.shared.transcription.whisper_api import WhisperAPITranscriber
from clipdeck.shared.transcription.whisper_local import WhisperLocalTranscriber


def get_transcriber(
    provider: str = "whisper_local",
    api_key: str | None = None,
    model: str | None = None,
) -> Transcriber:
    """Return a configured Transcriber instance.

    Providers:
    - 'whisper_local' (default): faster-whisper on CPU/GPU
    - 'whisper_api' / 'openai': OpenAI Whisper API
    - 'deepgram': Deepgram Nova-2
    """
    p = provider.lower().replace("-", "_")

    if p in ("whisper_local", "local", "faster_whisper"):
        return WhisperLocalTranscriber(model_size=model or "base")

    elif p in ("whisper_api", "openai"):
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("OpenAI API key required for Whisper API transcription")
        return WhisperAPITranscriber(api_key=key, model=model or "whisper-1")

    elif p in ("deepgram", "deepgram_api", "nova_2"):
        key = api_key or os.getenv("DEEPGRAM_API_KEY", "")
        if not key:
            raise ValueError("Deepgram API key required for Deepgram transcription")
        return DeepgramTranscriber(api_key=key, model=model or "nova-2")

    else:
        raise ValueError(f"Unknown transcription provider: {provider}")
