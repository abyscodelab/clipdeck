"""Twitch Chat Reader via IRC (anonymous read-only or authenticated).

Connects to Twitch IRC over TLS or plain TCP, joins the target channel,
requests Twitch IRC tags (badges, bits, emotes), and yields parsed ChatMessage instances.
Automatically handles PING/PONG and reconnects with exponential backoff.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import ssl
import time
from typing import AsyncIterator

from clipdeck.shared import constants
from clipdeck.shared.platforms.base import ChatMessage, ChatReader, Platform

logger = logging.getLogger(__name__)

# Matches IRC message with optional tags:
# @badge-info=...;badges=...;bits=100;... :nick!nick@nick.tmi.twitch.tv PRIVMSG #channel :message
_IRC_MSG_RE = re.compile(
    r"^(?:@(?P<tags>[^\s]+)\s+)?:(?P<prefix>[^\s]+)\s+(?P<command>[^\s]+)(?:\s+(?P<params>[^:]+))?(?:\s*:(?P<trailing>.*))?$"
)


def _parse_tags(tags_str: str) -> dict[str, str]:
    tags = {}
    for part in tags_str.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            tags[k] = v
        else:
            tags[part] = ""
    return tags


class TwitchChatReader(ChatReader):
    """Asynchronous Twitch chat reader via IRC."""

    def __init__(
        self,
        channel: str,
        token: str | None = None,
        nick: str | None = None,
        use_ssl: bool = True,
    ) -> None:
        super().__init__(channel=channel.lower().lstrip("#"), platform=Platform.TWITCH)
        self.token = token
        self.nick = nick or f"justinfan{random.randint(10000, 99999)}"
        self.use_ssl = use_ssl

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._queue: asyncio.Queue[ChatMessage] = asyncio.Queue(maxsize=10000)
        self._listen_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Establish connection and start the background listener."""
        self._listen_task = asyncio.create_task(self._connection_loop())

    async def disconnect(self) -> None:
        """Close connection and stop tasks."""
        self.request_stop()
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        await self._close_transport()

    async def _close_transport(self) -> None:
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

    async def messages(self) -> AsyncIterator[ChatMessage]:
        """Yield chat messages continuously."""
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
        """Persistent connection loop with backoff retry."""
        retry_delay = 1.0
        while self._running:
            try:
                await self._open_connection()
                retry_delay = 1.0  # reset on successful connection
                await self._read_lines()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(
                    "Twitch IRC connection lost for %s: %s. Reconnecting in %.1fs...",
                    self.channel,
                    e,
                    retry_delay,
                )
                await self._close_transport()
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)

    async def _open_connection(self) -> None:
        host = constants.TWITCH_IRC_HOST
        if self.use_ssl:
            port = constants.TWITCH_IRC_PORT
            ssl_ctx = ssl.create_default_context()
            self._reader, self._writer = await asyncio.open_connection(
                host, port, ssl=ssl_ctx
            )
        else:
            port = constants.TWITCH_IRC_PORT_PLAIN
            self._reader, self._writer = await asyncio.open_connection(host, port)

        logger.info("Connected to Twitch IRC for channel #%s as %s", self.channel, self.nick)

        # Send capabilities request for tags and commands
        await self._send_raw("CAP REQ :twitch.tv/tags twitch.tv/commands")

        if self.token:
            clean_token = self.token if self.token.startswith("oauth:") else f"oauth:{self.token}"
            await self._send_raw(f"PASS {clean_token}")
        else:
            await self._send_raw("PASS SCHMOOPIE")

        await self._send_raw(f"NICK {self.nick}")
        await self._send_raw(f"JOIN #{self.channel}")

    async def _send_raw(self, line: str) -> None:
        if self._writer:
            self._writer.write(f"{line}\r\n".encode("utf-8"))
            await self._writer.drain()

    async def _read_lines(self) -> None:
        assert self._reader is not None
        while self._running:
            line_bytes = await self._reader.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue

            # Handle PING keepalive
            if line.startswith("PING"):
                pong_arg = line.split(" ", 1)[1] if " " in line else ""
                await self._send_raw(f"PONG {pong_arg}")
                continue

            msg = self._parse_irc_line(line)
            if msg:
                try:
                    self._queue.put_nowait(msg)
                except asyncio.QueueFull:
                    try:
                        self._queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    self._queue.put_nowait(msg)

    def _parse_irc_line(self, raw_line: str) -> ChatMessage | None:
        match = _IRC_MSG_RE.match(raw_line)
        if not match:
            return None

        command = match.group("command")
        tags_raw = match.group("tags") or ""
        tags = _parse_tags(tags_raw)
        now = time.time()

        if command == "PRIVMSG":
            text = match.group("trailing") or ""
            prefix = match.group("prefix") or ""
            username = tags.get("display-name") or (prefix.split("!")[0] if "!" in prefix else prefix)

            # Check badges and tags
            badges = tags.get("badges", "")
            is_sub = "subscriber" in badges or tags.get("subscriber") == "1"
            is_mod = "moderator" in badges or tags.get("mod") == "1"

            bits_val = int(tags.get("bits", "0") or 0)

            return ChatMessage(
                text=text,
                username=username,
                timestamp=now,
                is_sub=is_sub,
                is_mod=is_mod,
                bits=bits_val,
                platform=Platform.TWITCH,
                raw={"tags": tags, "line": raw_line},
            )

        elif command == "USERNOTICE":
            # Sub gift or resub notice
            msg_id = tags.get("msg-id", "")
            username = tags.get("display-name") or tags.get("login", "anonymous")
            text = match.group("trailing") or ""

            sub_gift_count = 0
            if msg_id in ("subgift", "anonsubgift"):
                sub_gift_count = 1
            elif msg_id in ("submysterygift", "anonsubmysterygift"):
                sub_gift_count = int(tags.get("msg-param-mass-gift-count", "1") or 1)

            return ChatMessage(
                text=text if text else f"[Sub Event: {msg_id}]",
                username=username,
                timestamp=now,
                is_sub=True,
                is_mod=False,
                bits=0,
                sub_gift_count=sub_gift_count,
                platform=Platform.TWITCH,
                raw={"tags": tags, "msg_id": msg_id},
            )

        return None
