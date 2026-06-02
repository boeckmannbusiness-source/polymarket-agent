import json
import uuid
from datetime import datetime, timezone
from typing import Any
from collections import OrderedDict

from app.redis import get_redis
from app.core.logging import logger

EVENT_STORE_KEY = "event_store"
EVENT_STORE_MAXLEN = 50000


class EventStore:
    @staticmethod
    def make_event_record(
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        sequence: int | None = None,
    ) -> dict[str, Any]:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "sequence": sequence or 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": json.dumps(payload),
        }

    @staticmethod
    async def store(record: dict[str, Any]) -> str:
        r = await get_redis()
        event_id = record.get("event_id", str(uuid.uuid4()))
        data = {k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v)) for k, v in record.items()}
        await r.xadd(EVENT_STORE_KEY, data, maxlen=EVENT_STORE_MAXLEN, approximate=True)

        index_key = f"event_idx:{record.get('entity_type', 'unknown')}:{record.get('entity_id', 'unknown')}"
        await r.xadd(index_key, data, maxlen=1000, approximate=True)

        return event_id

    @staticmethod
    async def replay(
        from_ts: str | None = None,
        to_ts: str | None = None,
        event_type: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        r = await get_redis()

        if entity_type and entity_id:
            index_key = f"event_idx:{entity_type}:{entity_id}"
            try:
                raw = await r.xrevrange(index_key, max="+", min="-", count=limit)
            except Exception:
                raw = []
        else:
            raw = await r.xrevrange(EVENT_STORE_KEY, max="+", min="-", count=limit)

        results = []
        for msg_id, fields in raw:
            event = dict(fields)
            event["redis_id"] = msg_id
            try:
                event["payload"] = json.loads(event.get("payload", "{}"))
            except (json.JSONDecodeError, TypeError):
                pass

            if from_ts and event.get("timestamp", "") < from_ts:
                continue
            if to_ts and event.get("timestamp", "") > to_ts:
                continue
            if event_type and event.get("event_type") != event_type:
                continue

            results.append(event)

        return results[:limit]

    @staticmethod
    async def replay_by_time_range(
        from_ts: str,
        to_ts: str,
        event_type: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        return await EventStore.replay(from_ts=from_ts, to_ts=to_ts, event_type=event_type, limit=limit)


event_store = EventStore()


class DedupCache:
    def __init__(self, max_size: int = 10000):
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._max_size = max_size

    def check_and_set(self, key: str) -> bool:
        if key in self._cache:
            self._cache.move_to_end(key)
            return False
        self._cache[key] = datetime.now(timezone.utc).timestamp()
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
        return True

    def is_duplicate(self, key: str) -> bool:
        return key in self._cache

    def clear(self):
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        return 0.0


dedup_cache = DedupCache()
