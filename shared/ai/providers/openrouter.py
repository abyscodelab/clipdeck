"""OpenRouter unified LLM provider client."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from clipdeck.shared.ai.base import AIProvider, CompletionResult

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(AIProvider):
    """Client for routing through OpenRouter.ai."""

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-3.5-sonnet",
    ) -> None:
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
            "HTTP-Referer": "https://clipdeck.app",
            "X-Title": "ClipDeck",
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
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error("OpenRouter API error (%d): %s", resp.status, err_text)
                    raise RuntimeError(f"OpenRouter API failed: {err_text}")
                data = await resp.json()

        choices = data.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""

        usage = data.get("usage", {})
        inp = usage.get("prompt_tokens", 0)
        out = usage.get("completion_tokens", 0)

        # Average estimation ~$3 / $15 per M
        cost = (inp * 0.000003) + (out * 0.000015)

        return CompletionResult(
            content=content,
            input_tokens=inp,
            output_tokens=out,
            model=self.model,
            cost_usd=round(cost, 6),
        )
