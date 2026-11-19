"""Kick public API helpers and LiveChecker."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from clipdeck.shared import constants
from clipdeck.shared.platforms.base import LiveChecker, Platform, StreamInfo

logger = logging.getLogger(__name__)


class KickAPI(LiveChecker):
    """Kick API client implementing LiveChecker."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # Kick may require standard browser user-agent headers
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
            }
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_channel_data(self, slug: str) -> dict[str, Any]:
        """Fetch full channel metadata from /api/v2/channels/{slug}."""
        session = await self._get_session()
        url = f"{constants.KICK_API_BASE}/channels/{slug.lower().strip()}"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning("Kick channel %s returned status %d", slug, resp.status)
        except Exception as e:
            logger.error("Failed to query Kick channel %s: %s", slug, e)
        return {}

    async def get_chatroom_id(self, slug: str) -> int | None:
        """Fetch the chatroom ID required for Kick Pusher subscription."""
        data = await self.get_channel_data(slug)
        chatroom = data.get("chatroom")
        if chatroom and "id" in chatroom:
            return int(chatroom["id"])
        return None

    # ----------------------------------------------------------------------
    # LiveChecker implementation
    # ----------------------------------------------------------------------

    async def is_live(self, channel: str) -> StreamInfo:
        """Check live status for a Kick streamer."""
        slug = channel.lower().strip()
        data = await self.get_channel_data(slug)

        livestream = data.get("livestream")
        user = data.get("user", {})
        channel_id = str(data.get("id", user.get("id", "")))

        if livestream and isinstance(livestream, dict):
            # Stream is currently active
            categories = livestream.get("categories", [])
            category_name = categories[0].get("name", "") if categories else ""
            thumb = livestream.get("thumbnail", {}).get("url")

            return StreamInfo(
                platform=Platform.KICK,
                channel_name=slug,
                channel_id=channel_id,
                title=livestream.get("session_title", ""),
                game=category_name,
                viewer_count=livestream.get("viewer_count", 0),
                is_live=True,
                started_at=livestream.get("created_at"),
                stream_url=f"https://kick.com/{slug}",
                thumbnail_url=thumb,
            )

        return StreamInfo(
            platform=Platform.KICK,
            channel_name=slug,
            channel_id=channel_id,
            is_live=False,
            stream_url=f"https://kick.com/{slug}",
        )

    async def batch_check(self, channels: list[str]) -> list[StreamInfo]:
        """Check status of multiple Kick channels concurrently."""
        tasks = [self.is_live(c) for c in channels]
        return await asyncio.gather(*tasks)
