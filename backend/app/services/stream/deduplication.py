from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any


class EventDeduplicator:
    def __init__(self, max_size: int = 10000):
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._total = 0

    def is_duplicate(self, event: dict[str, Any]) -> bool:
        event_id = event.get("event_id", "")
        if not event_id:
            return False

        self._total += 1
        if event_id in self._cache:
            self._cache.move_to_end(event_id)
            self._hits += 1
            return True

        self._cache[event_id] = datetime.now(timezone.utc).timestamp()
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
        return False

    def mark_seen(self, event_id: str):
        if not event_id:
            return
        self._total += 1
        self._cache[event_id] = datetime.now(timezone.utc).timestamp()
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    @property
    def hit_rate(self) -> float:
        if self._total == 0:
            return 0.0
        return self._hits / self._total

    @property
    def size(self) -> int:
        return len(self._cache)

    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._total = 0


event_dedup = EventDeduplicator()
