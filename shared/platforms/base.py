"""Abstract base classes for platform adapters.

Every platform (Twitch, Kick, YouTube) implements these interfaces so the
worker orchestration layer can treat them uniformly.
"""

from __future__ import annotations

import abc
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Platform(str, Enum):
    TWITCH = "twitch"
    KICK = "kick"
    YOUTUBE = "youtube"


class StreamStatus(str, Enum):
    LIVE = "live"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Data classes shared across all platforms
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ChatMessage:
    """A single chat message from any platform."""

    text: str
    username: str
    timestamp: float
    is_sub: bool = False
    is_mod: bool = False
    bits: int = 0
    sub_gift_count: int = 0
    platform: Platform = Platform.TWITCH
    raw: dict | None = None


@dataclass(slots=True)
class StreamInfo:
    """Current stream metadata."""

    platform: Platform
    channel_name: str
    channel_id: str
    title: str = ""
    game: str = ""
    viewer_count: int = 0
    is_live: bool = False
    started_at: str | None = None
    stream_url: str | None = None
    thumbnail_url: str | None = None


# ---------------------------------------------------------------------------
# Abstract base classes
# ---------------------------------------------------------------------------

class ChatReader(abc.ABC):
    """Reads chat messages from a live stream.

    Implementations are async context managers that yield ``ChatMessage``
    objects forever until stopped or the stream goes offline.
    """

    def __init__(self, channel: str, platform: Platform) -> None:
        self.channel = channel
        self.platform = platform
        self._running = False
        self._stop_event = asyncio.Event()

    async def __aenter__(self) -> ChatReader:
        self._running = True
        self._stop_event.clear()
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._running = False
        self._stop_event.set()
        await self.disconnect()

    # -- abstract ----------------------------------------------------------

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish the connection (IRC, WebSocket, HTTP polling …)."""

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Cleanly tear down the connection."""

    @abc.abstractmethod
    def messages(self) -> AsyncIterator[ChatMessage]:
        """Async iterator that yields ``ChatMessage`` objects."""

    # -- helpers -----------------------------------------------------------

    def request_stop(self) -> None:
        """Signal the reader to stop at the next opportunity."""
        self._running = False
        self._stop_event.set()


class LiveChecker(abc.ABC):
    """Checks whether a channel is currently live."""

    @abc.abstractmethod
    async def is_live(self, channel: str) -> StreamInfo:
        """Return current stream info.  ``is_live`` may be False."""

    @abc.abstractmethod
    async def batch_check(self, channels: list[str]) -> list[StreamInfo]:
        """Check multiple channels in one API call when possible."""


class StreamRecorder(abc.ABC):
    """Records a live stream into segmented media files."""

    @abc.abstractmethod
    async def start(self) -> None: ...

    @abc.abstractmethod
    async def stop(self) -> None: ...

    @abc.abstractmethod
    def is_alive(self) -> bool: ...
