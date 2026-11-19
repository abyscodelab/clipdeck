"""YouTube Data API v3 client and LiveChecker."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from clipdeck.shared import constants
from clipdeck.shared.platforms.base import LiveChecker, Platform, StreamInfo

logger = logging.getLogger(__name__)


class YouTubeAPI(LiveChecker):
    """YouTube Data API v3 client."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_active_broadcast(self, channel_id: str) -> dict[str, Any] | None:
        """Find active live broadcast video for a YouTube channel."""
        if not self.api_key:
            logger.warning("YouTube API key not configured")
            return None

        session = await self._get_session()
        url = f"{constants.YOUTUBE_API_BASE}/search"
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "eventType": "live",
            "type": "video",
            "key": self.api_key,
        }

        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("items", [])
                    if items:
                        return items[0]
                else:
                    body = await resp.text()
                    logger.warning("YouTube search live failed (%d): %s", resp.status, body)
        except Exception as e:
            logger.error("Error searching YouTube live for %s: %s", channel_id, e)
        return None

    async def get_video_details(self, video_id: str) -> dict[str, Any] | None:
        """Fetch video details including liveStreamingDetails (activeLiveChatId, viewers)."""
        if not self.api_key:
            return None

        session = await self._get_session()
        url = f"{constants.YOUTUBE_API_BASE}/videos"
        params = {
            "part": "snippet,liveStreamingDetails",
            "id": video_id,
            "key": self.api_key,
        }

        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("items", [])
                    if items:
                        return items[0]
        except Exception as e:
            logger.error("Error fetching YouTube video details for %s: %s", video_id, e)
        return None

    # ----------------------------------------------------------------------
    # LiveChecker implementation
    # ----------------------------------------------------------------------

    async def is_live(self, channel: str) -> StreamInfo:
        """Check if a YouTube channel is currently broadcasting live."""
        channel_id = channel.strip()
        broadcast = await self.get_active_broadcast(channel_id)
        if not broadcast:
            return StreamInfo(
                platform=Platform.YOUTUBE,
                channel_name=channel_id,
                channel_id=channel_id,
                is_live=False,
            )

        video_id = broadcast.get("id", {}).get("videoId", "")
        snippet = broadcast.get("snippet", {})
        details = await self.get_video_details(video_id) if video_id else None

        viewers = 0
        started_at = None
        if details:
            live_details = details.get("liveStreamingDetails", {})
            viewers = int(live_details.get("concurrentViewers", 0))
            started_at = live_details.get("actualStartTime")

        thumb = snippet.get("thumbnails", {}).get("high", {}).get("url")

        return StreamInfo(
            platform=Platform.YOUTUBE,
            channel_name=snippet.get("channelTitle", channel_id),
            channel_id=channel_id,
            title=snippet.get("title", ""),
            game="",
            viewer_count=viewers,
            is_live=True,
            started_at=started_at,
            stream_url=f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
            thumbnail_url=thumb,
        )

    async def batch_check(self, channels: list[str]) -> list[StreamInfo]:
        """Check multiple YouTube channels concurrently."""
        tasks = [self.is_live(c) for c in channels]
        return await asyncio.gather(*tasks)
