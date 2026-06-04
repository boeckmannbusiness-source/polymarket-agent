from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger, _correlation_id

_trade_id: ContextVar[str] = ContextVar("trade_id", default="")
_order_id: ContextVar[str] = ContextVar("order_id", default="")
_fill_id: ContextVar[str] = ContextVar("fill_id", default="")
_incident_id: ContextVar[str] = ContextVar("incident_id", default="")
_strategy_id: ContextVar[str] = ContextVar("strategy_id", default="")

AUDIT_STREAM = "audit:log"
AUDIT_STREAM_MAXLEN = 100000

_CONTEXT_VARS = {
    "trade_id": _trade_id,
    "order_id": _order_id,
    "fill_id": _fill_id,
    "incident_id": _incident_id,
    "strategy_id": _strategy_id,
}


@contextmanager
def audit_context(**fields):
    tokens = {}
    for name, var in _CONTEXT_VARS.items():
        if name in fields:
            tokens[name] = var.set(str(fields[name]))
    try:
        yield
    finally:
        for name, token in tokens.items():
            _CONTEXT_VARS[name].reset(token)


async def emit(
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any] | None = None,
):
    record = {
        "correlation_id": _correlation_id.get(),
        "trade_id": _trade_id.get(),
        "order_id": _order_id.get(),
        "fill_id": _fill_id.get(),
        "incident_id": _incident_id.get(),
        "strategy_id": _strategy_id.get(),
        "event_type": f"audit.{event_type}",
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else "",
        "payload": payload or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"audit.{event_type}", **record)
    await _persist_to_redis(record)


async def _persist_to_redis(record: dict):
    try:
        from app.redis import get_redis
        r = await get_redis()
        await r.xadd(AUDIT_STREAM, record, maxlen=AUDIT_STREAM_MAXLEN, approximate=True)
    except Exception:
        pass
