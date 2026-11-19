"""YouTube Live Chat Reader via Google Data API v3 liveChatMessages.

Polls the YouTube Live Chat API respecting returned polling intervals
and page tokens, converting messages to uniform ChatMessage instances.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator

import aiohttp

from clipdeck.shared import constants
from clipdeck.shared.platforms.base import ChatMessage, ChatReader, Platform
from clipdeck.shared.platforms.youtube.api import YouTubeAPI

logger = logging.getLogger(__name__)


class YouTubeChatReader(ChatReader):
    """Asynchronous YouTube Live Chat reader using liveChatMessages polling."""

    def __init__(
        self,
        channel: str,
        api_key: str,
        video_id: str | None = None,
        live_chat_id: str | None = None,
    ) -> None:
        super().__init__(channel=channel.strip(), platform=Platform.YOUTUBE)
        self.api_key = api_key
        self.video_id = video_id
        self.live_chat_id = live_chat_id

        self._youtube_api = YouTubeAPI(api_key=api_key)
        self._session: aiohttp.ClientSession | None = None
        self._queue: asyncio.Queue[ChatMessage] = asyncio.Queue(maxsize=10000)
        self._poll_task: asyncio.Task | None = None
        self._next_page_token: str | None = None

    async def connect(self) -> None:
        """Resolve live_chat_id if not present, and launch polling loop."""
        if not self.live_chat_id:
            if not self.video_id:
                broadcast = await self._youtube_api.get_active_broadcast(self.channel)
                if not broadcast:
                    raise RuntimeError(f"No active live broadcast found for YouTube channel {self.channel}")
                self.video_id = broadcast.get("id", {}).get("videoId")

            if self.video_id:
                details = await self._youtube_api.get_video_details(self.video_id)
                if details:
                    self.live_chat_id = (
                        details.get("liveStreamingDetails", {}).get("activeLiveChatId")
                    )

        if not self.live_chat_id:
            raise RuntimeError(f"Could not obtain activeLiveChatId for YouTube channel {self.channel}")

        self._session = aiohttp.ClientSession()
        self._poll_task = asyncio.create_task(self._polling_loop())

    async def disconnect(self) -> None:
        """Halt polling and cleanup resources."""
        self.request_stop()
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._session and not self._session.closed:
            await self._session.close()
        await self._youtube_api.close()

    async def messages(self) -> AsyncIterator[ChatMessage]:
        """Yield parsed chat messages."""
        while self._running:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield msg
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def _polling_loop(self) -> None:
        poll_interval_secs = 5.0
        while self._running:
            try:
                assert self._session is not None
                url = f"{constants.YOUTUBE_API_BASE}/liveChat/messages"
                params: dict[str, str] = {
                    "liveChatId": self.live_chat_id or "",
                    "part": "snippet,authorDetails",
                    "key": self.api_key,
                }
                if self._next_page_token:
                    params["pageToken"] = self._next_page_token

                async with self._session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._next_page_token = data.get("nextPageToken")
                        poll_ms = data.get("pollingIntervalMillis", 5000)
                        poll_interval_secs = max(2.0, poll_ms / 1000.0)

                        now = time.time()
                        for item in data.get("items", []):
                            chat_msg = self._parse_item(item, now)
                            if chat_msg:
                                self._queue.put_nowait(chat_msg)
                    elif resp.status in (403, 404):
                        body = await resp.text()
                        logger.warning("YouTube chat error (%d): %s", resp.status, body)
                        poll_interval_secs = 15.0
                    else:
                        poll_interval_secs = 10.0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in YouTube chat polling loop: %s", e)
                poll_interval_secs = 10.0

            await asyncio.sleep(poll_interval_secs)

    def _parse_item(self, item: dict, default_ts: float) -> ChatMessage | None:
        snippet = item.get("snippet", {})
        author = item.get("authorDetails", {})

        msg_type = snippet.get("type")
        display_text = snippet.get("displayMessage", "")
        username = author.get("displayName", "anonymous")
        is_sub = author.get("isChatSponsor", False)
        is_mod = author.get("isChatModerator", False) or author.get("isChatOwner", False)

        sub_gift_count = 0
        bits = 0

        if msg_type == "superChatEvent":
            super_chat = snippet.get("superChatDetails", {})
            amount = super_chat.get("amountMicros", 0)
            bits = int(amount) // 10000  # proxy equivalent
        elif msg_type == "membershipGiftingEvent":
            gifting = snippet.get("membershipGiftingDetails", {})
            sub_gift_count = gifting.get("giftMembershipsCount", 1)

        return ChatMessage(
            text=display_text,
            username=username,
            timestamp=default_ts,
            is_sub=is_sub,
            is_mod=is_mod,
            bits=bits,
            sub_gift_count=sub_gift_count,
            platform=Platform.YOUTUBE,
            raw=item,
        )
