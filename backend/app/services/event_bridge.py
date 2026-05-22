import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.events import EventBus
from app.core.logging import logger
from app.database import async_session_factory
from app.models import MarketEvent, Market


class EventPersistenceBridge:
    def __init__(self):
        self.running = False
        self._tasks: list[asyncio.Task] = []
        self._processed = 0
        self._persisted_count = 0
        self._failed_count = 0
        self._dlq: list[dict] = []

    async def start(self):
        self.running = True
        self._tasks.append(asyncio.create_task(self._consume_market_events()))
        logger.info("event_persistence_bridge_started")

    async def stop(self):
        self.running = False
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _consume_market_events(self):
        r = await EventBus.subscribe_to_stream("market:data", "persistence_bridge", "writer_1")
        while self.running:
            try:
                messages = await EventBus.read_stream(r, "market:data", "persistence_bridge", "writer_1", block=5000)
                for msg in messages:
                    await self._persist_market_event(msg)
                    await EventBus.ack_message(r, "market:data", "persistence_bridge", msg["id"])
                    self._processed += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("persist_market_events_error", error=str(e))
                await asyncio.sleep(1)

    async def _persist_market_event(self, msg: dict):
        data = msg.get("data", {})
        if not data:
            return
        event_type = msg.get("event_type", "unknown")
        if event_type == "trade":
            await self._persist_trade_event(data)
        elif event_type == "market_metadata":
            await self._persist_market_metadata(data)

    async def _persist_trade_event(self, data: dict):
        condition_id = data.get("condition_id") or data.get("conditionId")
        market_id = None
        if condition_id:
            async with async_session_factory() as db:
                try:
                    result = await db.execute(
                        select(Market).where(Market.condition_id == condition_id)
                    )
                    m = result.scalar_one_or_none()
                    if m:
                        market_id = m.id
                except Exception:
                    pass

        ts = _parse_timestamp(data.get("timestamp"))

        async with async_session_factory() as db:
            try:
                event = MarketEvent(
                    market_id=market_id,
                    event_type="trade",
                    event_data=data,
                    price=float(data["price"]) if data.get("price") else None,
                    size=float(data["size"]) if data.get("size") else None,
                    maker_address=data.get("maker"),
                    taker_address=data.get("taker"),
                    outcome=data.get("outcome"),
                    transaction_hash=data.get("transaction_hash"),
                    timestamp=ts,
                )
                db.add(event)
                await db.commit()
                self._persisted_count += 1
            except Exception as e:
                await db.rollback()
                self._failed_count += 1
                logger.debug("trade_event_persist_failed", error=str(e))
                await self._dead_letter("trade", data, str(e))

    async def _persist_market_metadata(self, data: dict):
        async with async_session_factory() as db:
            try:
                from app.services.market_service import MarketService
                condition_id = data.get("conditionId") or data.get("condition_id")
                if not condition_id:
                    return
                service = MarketService(db)
                await service.upsert_market(
                    condition_id,
                    slug=data.get("slug"),
                    title=data.get("question") or data.get("title"),
                    description=data.get("description"),
                    outcomes=data.get("outcomes"),
                    volume=float(data["volume"]) if data.get("volume") else None,
                    liquidity=float(data["liquidity"]) if data.get("liquidity") else None,
                    clob_token_ids=_parse_clob_ids(data.get("clobTokenIds") or data.get("clob_token_ids")),
                    resolved=bool(data.get("closed", False)),
                    resolution=data.get("resolvedOutcome") or data.get("resolution"),
                )
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.debug("market_metadata_persist_skipped", error=str(e))

    async def _dead_letter(self, event_type: str, data: dict, error: str):
        entry = {
            "event_type": event_type,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        self._dlq.append(entry)
        if len(self._dlq) > 1000:
            self._dlq = self._dlq[-500:]
        try:
            from app.redis import get_redis
            r = await get_redis()
            await r.xadd("market:data:dlq", entry, maxlen=5000)
        except Exception:
            pass

    @property
    def stats(self):
        return {
            "events_processed": self._processed,
            "persisted_count": self._persisted_count,
            "failed_count": self._failed_count,
            "dlq_size": len(self._dlq),
        }


def _parse_timestamp(raw) -> datetime:
    if raw is None:
        return datetime.now(timezone.utc)
    try:
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw / 1000, tz=timezone.utc)
        s = str(raw).strip()
        if s.isdigit() or (s.replace(".", "").replace("-", "").isdigit()):
            return datetime.fromtimestamp(float(s) / 1000, tz=timezone.utc)
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError, OSError):
        return datetime.now(timezone.utc)


def _parse_clob_ids(raw) -> list[str] | None:
    if not raw:
        return None
    if isinstance(raw, list):
        return [str(t) for t in raw if t]
    if isinstance(raw, str):
        import json as _json
        try:
            parsed = _json.loads(raw)
            return [str(t) for t in parsed] if isinstance(parsed, list) else [raw]
        except (_json.JSONDecodeError, TypeError):
            return [raw]
    return None
