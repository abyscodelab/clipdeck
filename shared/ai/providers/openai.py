"""OpenAI GPT provider client."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from clipdeck.shared.ai.base import AIProvider, CompletionResult

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(AIProvider):
    """Client for OpenAI GPT models (e.g. gpt-4o, gpt-4o-mini)."""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                OPENAI_CHAT_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error("OpenAI API error (%d): %s", resp.status, err_text)
                    raise RuntimeError(f"OpenAI API failed: {err_text}")
                data = await resp.json()

        choices = data.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""

        usage = data.get("usage", {})
        inp = usage.get("prompt_tokens", 0)
        out = usage.get("completion_tokens", 0)

        # Estimate cost (gpt-4o: $2.50 / $10.00 per M; gpt-4o-mini: $0.15 / $0.60 per M)
        if "mini" in self.model:
            cost = (inp * 0.00000015) + (out * 0.0000006)
        else:
            cost = (inp * 0.0000025) + (out * 0.000010)

        return CompletionResult(
            content=content,
            input_tokens=inp,
            output_tokens=out,
            model=self.model,
            cost_usd=round(cost, 6),
        )
