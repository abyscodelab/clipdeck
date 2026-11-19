"""Abstract base classes and completion models for LLM providers."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CompletionResult:
    """Result returned by an AI provider completion."""

    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    cost_usd: float = 0.0


class AIProvider(abc.ABC):
    """Abstract interface for LLM completions."""

    @abc.abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> CompletionResult:
        """Execute a text or structured completion."""
        pass
