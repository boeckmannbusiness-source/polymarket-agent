import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.redis import get_redis


class EventBus:
    STREAMS = {
        "market:data": "*",
        "wallet:trade": "*",
        "whale:activity": "*",
        "signal:generated": "*",
        "trade:request": "*",
        "trade:execution": "*",
        "agent:event": "*",
        "system:alert": "*",
    }

    PUBSUB_CHANNELS = {
        "dashboard:markets",
        "dashboard:whales",
        "dashboard:signals",
        "dashboard:trades",
        "telegram:alerts",
    }

    @staticmethod
    def make_event(event_type: str, source: str, data: dict, correlation_id: str | None = None) -> dict:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "data": json.dumps(data),
        }

    @staticmethod
    async def publish(stream_or_channel: str, event_type: str, source: str, data: dict, correlation_id: str | None = None):
        r = await get_redis()
        event = EventBus.make_event(event_type, source, data, correlation_id)

        if stream_or_channel in EventBus.PUBSUB_CHANNELS:
            await r.publish(stream_or_channel, json.dumps(event))
        else:
            maxlen = settings.REDIS_STREAM_MAXLEN
            if settings.STREAM_TRIM_APPROX:
                await r.xadd(stream_or_channel, event, maxlen=int(maxlen), approximate=True)
            else:
                await r.xadd(stream_or_channel, event, maxlen=maxlen)

    @staticmethod
    async def subscribe_to_stream(stream: str, group: str, consumer: str):
        r = await get_redis()
        try:
            await r.xgroup_create(stream, group, id="0", mkstream=True)
        except Exception:
            from app.core.logging import logger
            logger.debug("consumer_group_exists_or_error", stream=stream, group=group)
        return r

    @staticmethod
    async def read_stream(
        r, stream: str, group: str, consumer: str, count: int = 10, block: int = 2000
    ) -> list[dict[str, Any]]:
        results = await r.xreadgroup(group, consumer, {stream: ">"}, count=count, block=block)
        messages = []
        if results:
            for stream_name, entries in results:
                for msg_id, msg_data in entries:
                    try:
                        msg_data["data"] = json.loads(msg_data.get("data", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        pass
                    messages.append({"stream": stream_name, "id": msg_id, **msg_data})
        return messages

    @staticmethod
    async def read_pending(r, stream: str, group: str, consumer: str, count: int = 100) -> list[dict[str, Any]]:
        results = await r.xpending_range(stream, group, min="-", max="+", count=count, consumername=consumer)
        messages = []
        for entry in results:
            msg_id = entry.get("message_id") if isinstance(entry, dict) else entry[0]
            msg_data = {}
            try:
                raw = await r.xrange(stream, min=msg_id, max=msg_id, count=1)
                if raw:
                    _, fields = raw[0]
                    msg_data = dict(fields)
                    try:
                        msg_data["data"] = json.loads(msg_data.get("data", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        pass
            except Exception:
                pass
            messages.append({"stream": stream, "id": msg_id, **msg_data})
        return messages

    @staticmethod
    async def ack_message(r, stream: str, group: str, msg_id: str):
        await r.xack(stream, group, msg_id)

    @staticmethod
    async def subscribe_to_channel(channel: str):
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        return pubsub
