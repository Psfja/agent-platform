from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator


class ProjectEventBus:
    """单进程 SSE 事件总线；生产环境可替换为 Redis Pub/Sub。"""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def publish(self, project_id: str, event: str, data: dict[str, Any]) -> None:
        envelope = {
            "event": event,
            "projectId": project_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for queue in tuple(self._subscribers.get(project_id, set())):
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(envelope)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    @asynccontextmanager
    async def subscribe(self, project_id: str) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers[project_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[project_id].discard(queue)
            if not self._subscribers[project_id]:
                self._subscribers.pop(project_id, None)

    @staticmethod
    def encode(event: dict[str, Any]) -> str:
        event_name = event.get("event", "message")
        payload = json.dumps(event, ensure_ascii=False)
        return f"event: {event_name}\ndata: {payload}\n\n"


project_events = ProjectEventBus()
