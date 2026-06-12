import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.config import settings
from app.core.stream_registry import StreamRegistry
from app.redis import get_redis


class SchemaValidationError(Exception):
    def __init__(self, event_type: str, errors: list[str]):
        self.event_type = event_type
        self.errors = errors
        super().__init__(f"Schema validation failed for {event_type}: {'; '.join(errors)}")


def _validate_payload(event_type: str, data: dict) -> None:
    enforcement = settings.EVENT_SCHEMA_ENFORCEMENT
    if enforcement == "off":
        return

    try:
        from app.schemas.events import EVENT_PAYLOAD_MAP
        payload_model = EVENT_PAYLOAD_MAP.get(event_type)
        if payload_model is None:
            return
        payload_model.model_validate(data)
    except ValidationError as e:
        errors = [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]
        msg = f"Schema validation failed for {event_type}: {'; '.join(errors)}"
        if enforcement == "strict":
            raise SchemaValidationError(event_type, errors) from e
        from app.core.logging import logger
        logger.warning("schema_validation_warning", event_type=event_type, errors=errors)


class EventBus:
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
        is_pubsub = stream_or_channel in EventBus.PUBSUB_CHANNELS

        if not is_pubsub:
            _validate_payload(event_type, data)

        r = await get_redis()
        event = EventBus.make_event(event_type, source, data, correlation_id)

        if is_pubsub:
            await r.publish(stream_or_channel, json.dumps(event))
            return

        config = StreamRegistry.get(stream_or_channel)
        if config is not None:
            await r.xadd(stream_or_channel, event, maxlen=int(config.maxlen), approximate=config.trim_mode == "approximate")
        else:
            maxlen = settings.REDIS_STREAM_MAXLEN
            if settings.STREAM_TRIM_APPROX:
                await r.xadd(stream_or_channel, event, maxlen=int(maxlen), approximate=True)
            else:
                await r.xadd(stream_or_channel, event, maxlen=maxlen)

    @staticmethod
    async def subscribe_to_stream(stream: str, group: str, consumer: str):
        config = StreamRegistry.get(stream)
        if config is not None and group not in config.consumer_groups:
            raise ValueError(
                f"Consumer group '{group}' not in allowed groups for stream '{stream}'. "
                f"Allowed: {config.consumer_groups}"
            )
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
