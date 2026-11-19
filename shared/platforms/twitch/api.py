"""Twitch Helix API client.

Handles stream metadata querying, batch live checking, user lookup,
and official Twitch clip creation. Supports client credential auth.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from clipdeck.shared import constants
from clipdeck.shared.platforms.base import LiveChecker, Platform, StreamInfo, StreamStatus

logger = logging.getLogger(__name__)


class TwitchHelixAPI(LiveChecker):
    """Twitch Helix API client implementing LiveChecker."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        oauth_token: str | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._oauth_token = oauth_token
        self._token_expires_at: float = 0.0
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _ensure_token(self) -> str:
        """Fetch App Access Token if not provided or expired."""
        if self._oauth_token and self._token_expires_at == 0.0:
            # User provided static token
            return self._oauth_token

        if self._oauth_token and time.time() < self._token_expires_at - 60:
            return self._oauth_token

        if not self.client_id or not self.client_secret:
            raise ValueError("Twitch client_id and client_secret required to request App Token")

        session = await self._get_session()
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }
        async with session.post(url, data=params) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"Twitch OAuth token request failed: {data}")
            self._oauth_token = data["access_token"]
            self._token_expires_at = time.time() + float(data.get("expires_in", 3600))
            return self._oauth_token

    async def _get_headers(self) -> dict[str, str]:
        token = await self._ensure_token()
        return {
            "Client-Id": self.client_id or "",
            "Authorization": f"Bearer {token}",
        }

    # ----------------------------------------------------------------------
    # LiveChecker implementation
    # ----------------------------------------------------------------------

    async def is_live(self, channel: str) -> StreamInfo:
        """Check if a single channel is live."""
        res = await self.batch_check([channel])
        if res:
            return res[0]
        return StreamInfo(
            platform=Platform.TWITCH,
            channel_name=channel,
            channel_id="",
            is_live=False,
        )

    async def batch_check(self, channels: list[str]) -> list[StreamInfo]:
        """Check multiple channels (up to 100 per request) via Helix GET /streams."""
        if not channels:
            return []

        session = await self._get_session()
        clean_channels = [c.lower().lstrip("#") for c in channels][:100]

        params = [("user_login", c) for c in clean_channels]
        url = f"{constants.TWITCH_HELIX_BASE}/streams"

        channel_map: dict[str, StreamInfo] = {
            c: StreamInfo(
                platform=Platform.TWITCH,
                channel_name=c,
                channel_id="",
                is_live=False,
            )
            for c in clean_channels
        }

        try:
            headers = await self._get_headers()
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data.get("data", []):
                        login = item["user_login"].lower()
                        thumb = item.get("thumbnail_url", "").replace("{width}x{height}", "1280x720")
                        channel_map[login] = StreamInfo(
                            platform=Platform.TWITCH,
                            channel_name=item["user_login"],
                            channel_id=item["user_id"],
                            title=item.get("title", ""),
                            game=item.get("game_name", ""),
                            viewer_count=item.get("viewer_count", 0),
                            is_live=item.get("type") == "live",
                            started_at=item.get("started_at"),
                            stream_url=f"https://twitch.tv/{item['user_login']}",
                            thumbnail_url=thumb,
                        )
                else:
                    body = await resp.text()
                    logger.warning("Twitch /streams check failed (%d): %s", resp.status, body)
        except Exception as e:
            logger.error("Error during Twitch batch_check: %s", e)

        return list(channel_map.values())

    # ----------------------------------------------------------------------
    # Clips & Users
    # ----------------------------------------------------------------------

    async def create_clip(self, broadcaster_id: str) -> dict[str, Any]:
        """Trigger native Twitch clip creation via Helix API."""
        session = await self._get_session()
        headers = await self._get_headers()
        url = f"{constants.TWITCH_HELIX_BASE}/clips"
        params = {"broadcaster_id": broadcaster_id}

        async with session.post(url, params=params, headers=headers) as resp:
            data = await resp.json()
            if resp.status == 202 and "data" in data and data["data"]:
                return data["data"][0]  # {"id": clip_id, "edit_url": ...}
            logger.warning("Failed to create Twitch clip: %s", data)
            return {}
