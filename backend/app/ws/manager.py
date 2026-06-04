import asyncio
import json
import time
from typing import Any
from collections import defaultdict

from fastapi import WebSocket

from app.core.logging import logger
from app.services.stream.deduplication import event_dedup
from app.services.stream.event_store import event_store
from app.services.monitoring.latency_service import latency_tracker
from app.services.reliability.dead_letter_queue import dlq


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._filters: dict[WebSocket, dict[str, set[str]]] = {}
        self._lock = asyncio.Lock()
        self._sequences: dict[str, int] = defaultdict(int)
        self._backpressure: dict[WebSocket, float] = {}
        self._max_msgs_per_sec = 10

    async def connect(self, ws: WebSocket, channel: str):
        await ws.accept()
        async with self._lock:
            self._connections[channel].add(ws)
            self._filters.setdefault(ws, {}).setdefault("channels", set()).add(channel)
            self._backpressure[ws] = 0.0
        logger.debug("ws_client_connected", channel=channel)

    async def disconnect(self, ws: WebSocket, channel: str | None = None):
        async with self._lock:
            if channel:
                self._connections[channel].discard(ws)
            else:
                for ch in list(self._filters.get(ws, {}).get("channels", set())):
                    self._connections[ch].discard(ws)
            self._filters.pop(ws, None)
            self._backpressure.pop(ws, None)
        logger.debug("ws_client_disconnected", channel=channel or "all")

    async def subscribe(self, ws: WebSocket, channel: str, entity_ids: list[str] | None = None):
        async with self._lock:
            self._connections[channel].add(ws)
            self._filters.setdefault(ws, {}).setdefault("channels", set()).add(channel)
            if entity_ids:
                self._filters[ws].setdefault("entity_filters", set()).update(entity_ids)

    async def broadcast(self, channel: str, event: dict[str, Any], max_ops_per_sec: int = 10):
        if event_dedup.is_duplicate(event):
            logger.debug("dedup_dropped_event", channel=channel, event_id=event.get("event_id", ""))
            return

        event_id = event.get("event_id", "")
        self._sequences[event_id] = self._sequences.get("_global", 0) + 1
        event["sequence"] = self._sequences[event_id]

        await event_store.store(event)

        payload = json.dumps(event, default=str)
        async with self._lock:
            targets = list(self._connections.get(channel, set()))

        if not targets:
            return

        batch_size = max(1, max_ops_per_sec)
        now = time.time()
        sent = 0

        for ws in targets:
            last_send = self._backpressure.get(ws, 0)
            if now - last_send < (1.0 / self._max_msgs_per_sec):
                continue

            if not self._should_send(ws, event):
                continue

            try:
                await ws.send_text(payload)
                self._backpressure[ws] = now
                sent += 1
            except Exception as ex:
                await dlq.push("ws_publish", "ws.send_failed", {"channel": channel, "event_id": event.get("event_id", "")}, str(ex))
                await self.disconnect(ws, channel)

            if sent >= batch_size:
                await asyncio.sleep(0.05)

    def _should_send(self, ws: WebSocket, event: dict) -> bool:
        filters = self._filters.get(ws)
        if not filters:
            return True
        entity_filters = filters.get("entity_filters", set())
        if not entity_filters:
            return True
        entity_id = event.get("entity_id", "")
        return entity_id in entity_filters

    async def broadcast_event(self, event: dict, channels: list[str] | None = None):
        target_channels = channels or [event.get("channel", "portfolio")]
        for ch in target_channels:
            await self.broadcast(ch, event)

    @property
    def connection_count(self) -> int:
        return len(self._filters)

    def reset_sequence(self):
        self._sequences.clear()


manager = ConnectionManager()
