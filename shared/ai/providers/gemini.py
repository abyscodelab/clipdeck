"""Google Gemini provider client."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from clipdeck.shared.ai.base import AIProvider, CompletionResult

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(AIProvider):
    """Client for Google Gemini models (e.g. gemini-1.5-flash, gemini-1.5-pro)."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        self.api_key = api_key
        self.model = model

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2500,
    ) -> CompletionResult:
        url = f"{GEMINI_BASE_URL}/{self.model}:generateContent?key={self.api_key}"

        contents = []
        if system_prompt:
            # Gemini supports system_instruction
            pass

        contents.append({"role": "user", "parts": [{"text": prompt}]})

        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error("Gemini API error (%d): %s", resp.status, err_text)
                    raise RuntimeError(f"Gemini API failed: {err_text}")
                data = await resp.json()

        candidates = data.get("candidates", [])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for p in parts:
                text += p.get("text", "")

        usage = data.get("usageMetadata", {})
        inp = usage.get("promptTokenCount", 0)
        out = usage.get("candidatesTokenCount", 0)

        cost = (inp * 0.000000075) + (out * 0.00000030)

        return CompletionResult(
            content=text,
            input_tokens=inp,
            output_tokens=out,
            model=self.model,
            cost_usd=round(cost, 6),
        )
