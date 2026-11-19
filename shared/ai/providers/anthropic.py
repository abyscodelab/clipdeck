"""Anthropic Claude provider client."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from clipdeck.shared.ai.base import AIProvider, CompletionResult

logger = logging.getLogger(__name__)

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


class AnthropicProvider(AIProvider):
    """Client for Anthropic Claude models (e.g. claude-3-5-sonnet-20241022)."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
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
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        user_content = prompt
        if json_mode and not ("json" in prompt.lower()):
            user_content += "\nRespond with valid JSON only."

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user_content}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with aiohttp.ClientSession() as session:
            async with session.post(
                ANTHROPIC_MESSAGES_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error("Anthropic API error (%d): %s", resp.status, err_text)
                    raise RuntimeError(f"Anthropic API failed: {err_text}")
                data = await resp.json()

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        usage = data.get("usage", {})
        inp = usage.get("input_tokens", 0)
        out = usage.get("output_tokens", 0)

        # Cost estimation: ~$3/M input, ~$15/M output for Sonnet 3.5
        cost = (inp * 0.000003) + (out * 0.000015)

        return CompletionResult(
            content=text,
            input_tokens=inp,
            output_tokens=out,
            model=self.model,
            cost_usd=round(cost, 6),
        )
