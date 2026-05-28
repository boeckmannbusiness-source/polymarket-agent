import asyncio
import hashlib
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
        self._retry_count = 0
        self._events_by_type: dict[str, int] = {}
        self._persisted_by_type: dict[str, int] = {}
        self._dropped_by_type: dict[str, int] = {}
        self._dlq: list[dict] = []

        # Duplicate detection (in-memory LRU)
        self._recent_hashes: set[str] = set()
        self._recent_hash_order: list[str] = []
        self._max_hash_cache = 2000
        self._duplicate_events_detected = 0

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self):
        self.running = True
        self._tasks.append(asyncio.create_task(self._consume_market_events()))
        logger.info("event_persistence_bridge_started")

    async def consume_pending(self, count: int = 100) -> dict:
        r = await EventBus.subscribe_to_stream("market:data", "persistence_bridge", "writer_1")
        messages = await EventBus.read_stream(r, "market:data", "persistence_bridge", "writer_1", count=count, block=1000)
        persisted = 0
        failed = 0
        for msg in messages:
            try:
                await self._persist_normalized_event(msg)
                await EventBus.ack_message(r, "market:data", "persistence_bridge", msg["id"])
                self._processed += 1
                persisted += 1
            except Exception as e:
                self._failed_count += 1
                failed += 1
                logger.error("force_consume_failed", error=str(e))
        return {"consumed": len(messages), "persisted": persisted, "failed": failed}

    async def stop(self):
        self.running = False
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    # ── Consumer loop ────────────────────────────────────────

    async def _consume_market_events(self):
        r = await EventBus.subscribe_to_stream("market:data", "persistence_bridge", "writer_1")
        while self.running:
            try:
                messages = await EventBus.read_stream(r, "market:data", "persistence_bridge", "writer_1", count=500, block=5000)
                for msg in messages:
                    event_type = msg.get("event_type", "unknown")
                    self._events_by_type[event_type] = self._events_by_type.get(event_type, 0) + 1
                    success = await self._persist_with_retry(msg)
                    if success:
                        await EventBus.ack_message(r, "market:data", "persistence_bridge", msg["id"])
                        self._processed += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                err_str = str(e)
                if "NOGROUP" in err_str or "no such consumer group" in err_str.lower():
                    logger.warning("consumer_group_missing_recreating")
                    r = await EventBus.subscribe_to_stream("market:data", "persistence_bridge", "writer_1")
                else:
                    logger.error("persist_market_events_error", error=err_str)
                await asyncio.sleep(1)

    # ── Retry + persist ──────────────────────────────────────

    async def _persist_with_retry(self, msg: dict, max_retries: int = 3) -> bool:
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                await self._persist_normalized_event(msg)
                return True
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    self._retry_count += 1
                    logger.debug("persist_retry", event_type=msg.get("event_type"), attempt=attempt + 1, error=str(e))
                    await asyncio.sleep(0.5 * (attempt + 1))
        self._failed_count += 1
        logger.error("persist_failed_all_retries", event_type=msg.get("event_type"), error=str(last_error))
        event_type = msg.get("event_type", "unknown")
        self._dropped_by_type[event_type] = self._dropped_by_type.get(event_type, 0) + 1
        await self._dead_letter(event_type, msg.get("data", {}), str(last_error))
        return False

    # ── Normalized event dispatcher ──────────────────────────

    async def _persist_normalized_event(self, msg: dict):
        data = msg.get("data", {})
        if not data:
            return
        event_type = msg.get("event_type", "unknown")

        # Bridge-level duplicate check
        event_hash = self._compute_event_hash(msg)
        if self._is_duplicate(event_hash):
            self._dropped_by_type[event_type] = self._dropped_by_type.get(event_type, 0) + 1
            return

        if event_type == "trade":
            await self._persist_trade(data)
        elif event_type == "price_change":
            await self._persist_price_change(data)
        elif event_type == "market_metadata":
            await self._persist_market_metadata(data)
        else:
            logger.debug("bridge_skipped_event_type", event_type=event_type)

    # ── Duplicate detection ──────────────────────────────────

    @staticmethod
    def _compute_event_hash(msg: dict) -> str:
        data = msg.get("data", {})
        raw = (
            str(msg.get("event_type", "")),
            str(data.get("condition_id", "")),
            str(data.get("asset_id", "")),
            str(data.get("price", "")),
            str(data.get("size", "")),
            str(data.get("timestamp", "")),
            str(data.get("wallet", "")),
        )
        return hashlib.sha256("|".join(raw).encode()).hexdigest()

    def _is_duplicate(self, event_hash: str) -> bool:
        if event_hash in self._recent_hashes:
            self._duplicate_events_detected += 1
            return True
        self._recent_hashes.add(event_hash)
        self._recent_hash_order.append(event_hash)
        if len(self._recent_hash_order) > self._max_hash_cache:
            old = self._recent_hash_order.pop(0)
            self._recent_hashes.discard(old)
        return False

    # ── Persisters ───────────────────────────────────────────

    async def _persist_trade(self, data: dict):
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
                        market_id = str(m.id)
                except Exception as e:
                    logger.error("market_lookup_failed_trade", condition_id=condition_id, error=str(e))

        ts = _parse_timestamp(data.get("timestamp"))
        price = data.get("price")
        if price is None:
            price = data.get("raw", {}).get("price")
        size = data.get("size")
        if size is None:
            size = data.get("raw", {}).get("size")

        async with async_session_factory() as db:
            try:
                event = MarketEvent(
                    market_id=market_id,
                    event_type="trade",
                    event_data=data,
                    price=_safe_float(price),
                    size=_safe_float(size),
                    maker_address=data.get("wallet") or data.get("maker"),
                    side=data.get("side"),
                    outcome=data.get("outcome"),
                    transaction_hash=data.get("transaction_hash") or data.get("tx_hash"),
                    timestamp=ts,
                )
                db.add(event)
                await db.commit()
                self._persisted_count += 1
                self._persisted_by_type["trade"] = self._persisted_by_type.get("trade", 0) + 1
            except Exception:
                await db.rollback()
                raise

    async def _persist_price_change(self, data: dict):
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
                        market_id = str(m.id)
                except Exception as e:
                    logger.error("market_lookup_failed_price_change", condition_id=condition_id, error=str(e))

        ts = _parse_timestamp(data.get("timestamp"))

        async with async_session_factory() as db:
            try:
                event = MarketEvent(
                    market_id=market_id,
                    event_type="price_change",
                    event_data=data,
                    price=_safe_float(data.get("price")),
                    size=None,
                    timestamp=ts,
                )
                db.add(event)
                await db.commit()
                self._persisted_count += 1
                self._persisted_by_type["price_change"] = self._persisted_by_type.get("price_change", 0) + 1
            except Exception:
                await db.rollback()
                raise

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
                    volume=_safe_float(data.get("volume")),
                    liquidity=_safe_float(data.get("liquidity")),
                    clob_token_ids=_parse_clob_ids(data.get("clobTokenIds") or data.get("clob_token_ids")),
                    resolved=bool(data.get("closed", False)),
                    resolution=data.get("resolvedOutcome") or data.get("resolution"),
                )
                await db.commit()
                self._persisted_by_type["market_metadata"] = self._persisted_by_type.get("market_metadata", 0) + 1
            except Exception:
                await db.rollback()
                raise

    # ── DLQ ──────────────────────────────────────────────────

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
        except Exception as e:
            logger.error("dlq_publish_failed", event_type=event_type, error=str(e))

    # ── Stats ────────────────────────────────────────────────

    @property
    def stats(self):
        return {
            "events_processed": self._processed,
            "persisted_count": self._persisted_count,
            "failed_count": self._failed_count,
            "retry_count": self._retry_count,
            "dlq_size": len(self._dlq),
            "events_by_type": dict(self._events_by_type),
            "persisted_by_type": dict(self._persisted_by_type),
            "dropped_by_type": dict(self._dropped_by_type),
            "duplicate_events_detected": self._duplicate_events_detected,
        }


# ── Helpers ──────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _parse_timestamp(raw) -> datetime:
    if raw is None:
        return datetime.now(timezone.utc)
    try:
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw / 1000, tz=timezone.utc)
        s = str(raw).strip() if raw else ""
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
