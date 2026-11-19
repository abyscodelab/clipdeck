"""Twitch EventSub WebSocket client.

Maintains a persistent connection to the Twitch EventSub WebSocket service
for near-instantaneous `stream.online` and `stream.offline` notifications.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Coroutine, Any

import aiohttp

logger = logging.getLogger(__name__)

TWITCH_EVENTSUB_WS_URL = "wss://eventsub.wss.twitch.tv/ws"


class TwitchEventSubWS:
    """Manages Twitch EventSub WebSocket connection and event dispatching."""

    def __init__(
        self,
        on_stream_online: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None,
        on_stream_offline: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self.on_stream_online = on_stream_online
        self.on_stream_offline = on_stream_offline
        self.session_id: str | None = None

        self._running = False
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._loop_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start EventSub listener in background."""
        self._running = True
        self._session = aiohttp.ClientSession()
        self._loop_task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Close connection and stop listener."""
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        retry_delay = 1.0
        while self._running:
            try:
                assert self._session is not None
                async with self._session.ws_connect(TWITCH_EVENTSUB_WS_URL) as ws:
                    self._ws = ws
                    retry_delay = 1.0
                    logger.info("Connected to Twitch EventSub WebSocket")

                    async for msg in ws:
                        if not self._running:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("EventSub WS error: %s. Reconnecting in %.1fs...", e, retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60.0)

    async def _handle_message(self, text: str) -> None:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return

        metadata = payload.get("metadata", {})
        msg_type = metadata.get("message_type")

        if msg_type == "session_welcome":
            session_info = payload.get("payload", {}).get("session", {})
            self.session_id = session_info.get("id")
            logger.info("EventSub session established. ID: %s", self.session_id)

        elif msg_type == "session_keepalive":
            pass

        elif msg_type == "notification":
            sub_type = payload.get("payload", {}).get("subscription", {}).get("type")
            event_data = payload.get("payload", {}).get("event", {})

            if sub_type == "stream.online" and self.on_stream_online:
                await self.on_stream_online(event_data)
            elif sub_type == "stream.offline" and self.on_stream_offline:
                await self.on_stream_offline(event_data)
