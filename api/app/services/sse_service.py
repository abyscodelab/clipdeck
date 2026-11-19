"""SSE event broadcaster — in-memory async pub/sub using asyncio.Queue."""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Fan-out broadcaster: one publish reaches every connected SSE client."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[str]] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Yield SSE-formatted strings as they arrive. Use as an async generator."""
        queue: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            self._subscribers.append(queue)
        try:
            while True:
                data = await queue.get()
                yield data
        except asyncio.CancelledError:
            pass
        finally:
            async with self._lock:
                self._subscribers.remove(queue)

    async def publish(self, event: str, data: dict[str, Any]) -> None:
        """Broadcast an SSE event to all connected clients."""
        payload = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        async with self._lock:
            dead: list[asyncio.Queue[str]] = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    dead.append(queue)
            for q in dead:
                self._subscribers.remove(q)
                logger.warning("Dropped slow SSE subscriber")

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# Global instance
broadcaster = SSEBroadcaster()
