"""Kick Chat Reader via Pusher WebSocket.

Connects to Kick's Pusher cluster to receive live chat events,
including messages, badges, and gifted subs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterator

import aiohttp

from clipdeck.shared import constants
from clipdeck.shared.platforms.base import ChatMessage, ChatReader, Platform
from clipdeck.shared.platforms.kick.api import KickAPI

logger = logging.getLogger(__name__)

KICK_PUSHER_WS_URL = (
    f"wss://{constants.KICK_PUSHER_HOST}/app/{constants.KICK_PUSHER_KEY}"
    "?protocol=7&client=js&version=7.4.0&flash=false"
)


class KickChatReader(ChatReader):
    """Asynchronous Kick chat reader via Pusher WebSocket."""

    def __init__(self, channel: str, chatroom_id: int | None = None) -> None:
        super().__init__(channel=channel.lower().strip(), platform=Platform.KICK)
        self.chatroom_id = chatroom_id
        self._kick_api = KickAPI()
        self._queue: asyncio.Queue[ChatMessage] = asyncio.Queue(maxsize=10000)
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._listen_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Resolve chatroom ID if necessary and start the WebSocket loop."""
        if not self.chatroom_id:
            resolved_id = await self._kick_api.get_chatroom_id(self.channel)
            if not resolved_id:
                raise ValueError(f"Could not resolve chatroom ID for Kick channel '{self.channel}'")
            self.chatroom_id = resolved_id

        self._session = aiohttp.ClientSession()
        self._listen_task = asyncio.create_task(self._connection_loop())

    async def disconnect(self) -> None:
        """Close connection and stop listener."""
        self.request_stop()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        await self._kick_api.close()

    async def messages(self) -> AsyncIterator[ChatMessage]:
        """Yield parsed ChatMessage objects."""
        while self._running:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield msg
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def _connection_loop(self) -> None:
        retry_delay = 1.0
        while self._running:
            try:
                assert self._session is not None
                async with self._session.ws_connect(KICK_PUSHER_WS_URL) as ws:
                    self._ws = ws
                    retry_delay = 1.0
                    logger.info("Connected to Kick Pusher for channel %s (chatroom %s)", self.channel, self.chatroom_id)

                    # Subscribe to the chatroom channel
                    sub_payload = {
                        "event": "pusher:subscribe",
                        "data": {
                            "auth": "",
                            "channel": f"chatrooms.{self.chatroom_id}.v2",
                        },
                    }
                    await ws.send_str(json.dumps(sub_payload))

                    async for msg in ws:
                        if not self._running:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_pusher_message(msg.data)
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(
                    "Kick Pusher connection lost for %s: %s. Reconnecting in %.1fs...",
                    self.channel,
                    e,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)

    async def _handle_pusher_message(self, raw_text: str) -> None:
        try:
            packet = json.loads(raw_text)
        except json.JSONDecodeError:
            return

        event = packet.get("event")
        data_raw = packet.get("data")

        # Handle Pusher ping
        if event == "pusher:ping" and self._ws and not self._ws.closed:
            await self._ws.send_str(json.dumps({"event": "pusher:pong", "data": {}}))
            return

        if not data_raw or not isinstance(data_raw, str):
            return

        try:
            event_data = json.loads(data_raw)
        except json.JSONDecodeError:
            return

        now = time.time()

        if event == "App\\Events\\ChatMessageEvent":
            content = event_data.get("content", "")
            sender = event_data.get("sender", {})
            username = sender.get("username", "anonymous")
            identity = sender.get("identity", {})
            badges = identity.get("badges", [])
            badge_types = {b.get("type") for b in badges if isinstance(b, dict)}

            is_sub = "subscriber" in badge_types
            is_mod = "moderator" in badge_types or "broadcaster" in badge_types

            chat_msg = ChatMessage(
                text=content,
                username=username,
                timestamp=now,
                is_sub=is_sub,
                is_mod=is_mod,
                platform=Platform.KICK,
                raw=event_data,
            )
            self._queue.put_nowait(chat_msg)

        elif event == "App\\Events\\GiftedSubscriptionsEvent":
            # Sub gift event
            gifts = event_data.get("gifted_usernames", [])
            count = len(gifts) if isinstance(gifts, list) and gifts else 1
            gifter = event_data.get("gifter_username", "anonymous")

            chat_msg = ChatMessage(
                text=f"[Kick Sub Gift: {count} subs]",
                username=gifter,
                timestamp=now,
                is_sub=True,
                sub_gift_count=count,
                platform=Platform.KICK,
                raw=event_data,
            )
            self._queue.put_nowait(chat_msg)
