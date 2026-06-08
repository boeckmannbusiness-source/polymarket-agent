import asyncio
import hashlib
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.core.events import EventBus
from app.core.logging import logger
from app.core.dedup import is_duplicate_event, mark_event_processed
from app.core.metrics import dlq_size, pel_depth, dlq_replay_success_total, dlq_replay_failures_total, recovery_loop_errors_total
from app.core.circuit_breaker import CircuitBreaker
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

        self._persist_semaphore = asyncio.Semaphore(5)
        self._circuit_breaker = CircuitBreaker("persistence_bridge", failure_threshold=10, window_seconds=60, recovery_seconds=30)

        # Duplicate detection (Redis-backed, L1 in-memory LRU)
        self._recent_hashes: set[str] = set()
        self._recent_hash_order: list[str] = []
        self._max_hash_cache = 2000
        self._duplicate_events_detected = 0
        self._redis_dedup_hits = 0
        self._redis_dedup_skipped = 0

        # DLQ replay stats
        self._dlq_replayed = 0
        self._dlq_replay_failures = 0

        # Pending recovery stats
        self._pending_claimed = 0
        self._pending_dlq_transferred = 0

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self):
        self.running = True
        self._tasks.append(asyncio.create_task(self._consume_market_events()))
        self._tasks.append(asyncio.create_task(self._pending_recovery_loop()))
        if settings.DLQ_REPLAY_ENABLED:
            self._tasks.append(asyncio.create_task(self._dlq_replay_loop()))
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

    # ── Pending message recovery ─────────────────────────────

    async def _pending_recovery_loop(self):
        await asyncio.sleep(30)
        while self.running:
            try:
                r = await EventBus.subscribe_to_stream("market:data", "persistence_bridge", "writer_1")
                pending_summary = await r.xpending("market:data", "persistence_bridge")
                if pending_summary:
                    total_pending = pending_summary[0] if isinstance(pending_summary, (list, tuple)) else 0
                    pel_depth.labels(stream="market:data", group="persistence_bridge").set(total_pending)
                    if total_pending > 0:
                        idle_ms = settings.PENDING_IDLE_TIMEOUT * 1000
                        claimed = await r.xautoclaim(
                            "market:data", "persistence_bridge", "writer_1",
                            min_idle_time=idle_ms,
                            count=settings.PENDING_CLAIM_COUNT,
                        )
                        if claimed and len(claimed) >= 2:
                            claimed_ids = claimed[1] if isinstance(claimed[1], list) else []
                            for msg_id, msg_data in claimed_ids:
                                if isinstance(msg_data, list):
                                    msg_data = dict(msg_data)
                                try:
                                    msg_data["data"] = msg_data.get("data", {})
                                    if isinstance(msg_data.get("data"), str):
                                        import json
                                        msg_data["data"] = json.loads(msg_data["data"])
                                except Exception:
                                    pass
                                msg = {"stream": "market:data", "id": msg_id, **msg_data}
                                success = await self._persist_with_retry(msg)
                                if success:
                                    await EventBus.ack_message(r, "market:data", "persistence_bridge", msg_id)
                                    self._processed += 1
                                    self._pending_claimed += 1
                                else:
                                    retry_key = f"bridge_retry:{msg_id}"
                                    retry_count = getattr(self, "_retry_map", {}).get(retry_key, 0) + 1
                                    if not hasattr(self, "_retry_map"):
                                        self._retry_map = {}
                                    self._retry_map[retry_key] = retry_count
                                    if retry_count > settings.PENDING_MAX_RETRIES:
                                        dlq_entry = {
                                            "original_stream": "market:data",
                                            "group": "persistence_bridge",
                                            "msg_id": msg_id,
                                            "retry_count": retry_count,
                                            "error": "max_retries_exceeded_in_recovery",
                                            "timestamp": datetime.now(timezone.utc).isoformat(),
                                        }
                                        try:
                                            await r.xadd(settings.PENDING_DLQ_STREAM, dlq_entry, maxlen=5000)
                                        except Exception:
                                            pass
                                        await EventBus.ack_message(r, "market:data", "persistence_bridge", msg_id)
                                        self._pending_dlq_transferred += 1
                                        logger.warning("bridge_pel_dlq", msg_id=msg_id, retry_count=retry_count)
                        logger.info(
                            "bridge_pel_cycle",
                            pending_total=total_pending,
                            claimed=self._pending_claimed,
                            dlq=self._pending_dlq_transferred,
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("bridge_pel_error", error=str(e))
            await asyncio.sleep(settings.PENDING_RECOVERY_INTERVAL)

    # ── Consumer loop ────────────────────────────────────────

    async def _consume_market_events(self):
        r = await EventBus.subscribe_to_stream("market:data", "persistence_bridge", "writer_1")
        while self.running:
            try:
                from app.core.system_mode import get_mode_manager
                mgr = get_mode_manager()
                if not mgr.can_process():
                    await asyncio.sleep(5)
                    continue

                cb_state = self._circuit_breaker.state
                if cb_state.name == "OPEN":
                    logger.warning("circuit_breaker_open", breaker=self._circuit_breaker.name)
                    await asyncio.sleep(5)
                    continue

                messages = await EventBus.read_stream(r, "market:data", "persistence_bridge", "writer_1", count=500, block=5000)
                for msg in messages:
                    event_type = msg.get("event_type", "unknown")
                    self._events_by_type[event_type] = self._events_by_type.get(event_type, 0) + 1
                    success = await self._persist_with_retry(msg)
                    if success:
                        if self._circuit_breaker.state.name == "HALF_OPEN":
                            self._circuit_breaker.record_success()
                    else:
                        self._circuit_breaker.record_failure()
                    await EventBus.ack_message(r, "market:data", "persistence_bridge", msg["id"])
                    if success:
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
        from app.core.system_mode import get_mode_manager
        if not get_mode_manager().can_write():
            return False

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                async with self._persist_semaphore:
                    await self._persist_normalized_event(msg)
                return True
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    self._retry_count += 1
                    logger.debug("persist_retry", event_type=msg.get("event_type"), attempt=attempt + 1, error=str(e))
                    await asyncio.sleep(0.5 * (attempt + 1))
        self._failed_count += 1
        self._circuit_breaker.record_failure()
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

        event_hash = self._compute_event_hash(msg)
        if await self._is_duplicate(event_hash):
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

    async def _is_duplicate(self, event_hash: str) -> bool:
        if event_hash in self._recent_hashes:
            self._duplicate_events_detected += 1
            return True
        if settings.DEDUP_REDIS_ENABLED:
            redis_dup = await is_duplicate_event(event_hash)
            if redis_dup:
                self._redis_dedup_hits += 1
                self._duplicate_events_detected += 1
                return True
            self._redis_dedup_skipped += 1
        self._recent_hashes.add(event_hash)
        self._recent_hash_order.append(event_hash)
        if len(self._recent_hash_order) > self._max_hash_cache:
            old = self._recent_hash_order.pop(0)
            self._recent_hashes.discard(old)
        await mark_event_processed(event_hash)
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
        dlq_size.labels(origin_stream="market:data").set(len(self._dlq))
        try:
            from app.redis import get_redis
            r = await get_redis()
            await r.xadd("market:data:dlq", entry, maxlen=5000)
        except Exception as e:
            logger.error("dlq_publish_failed", event_type=event_type, error=str(e))

    async def replay_dlq(self, max_entries: int = 100) -> dict:
        replayed = 0
        failed = 0
        skipped = 0
        dlq_size.labels(origin_stream="market:data").set(len(self._dlq))
        try:
            from app.redis import get_redis
            r = await get_redis()
            dlq_entries = await r.xrevrange("market:data:dlq", count=max_entries)
            for msg_id, raw in dlq_entries:
                if isinstance(raw, list):
                    raw = dict(raw)
                event_type = raw.get("event_type", "unknown")
                data_raw = raw.get("data", {})
                if isinstance(data_raw, str):
                    try:
                        import json
                        data_raw = json.loads(data_raw)
                    except Exception:
                        data_raw = {}
                try:
                    entry = raw.get("data", data_raw) if isinstance(raw.get("data"), dict) else data_raw
                    event_type_from_data = entry.get("event_type") if isinstance(entry, dict) else event_type
                    msg = {
                        "event_type": event_type_from_data or event_type,
                        "data": entry if isinstance(entry, dict) else {},
                    }
                    success = await self._persist_with_retry(msg)
                    if success:
                        await r.xack("market:data:dlq", "persistence_bridge", msg_id) if False else None
                        await r.xdel("market:data:dlq", msg_id)
                        replayed += 1
                        self._dlq_replayed += 1
                        dlq_replay_success_total.labels(origin_stream="market:data").inc()
                    else:
                        failed += 1
                        self._dlq_replay_failures += 1
                        dlq_replay_failures_total.labels(origin_stream="market:data").inc()
                        logger.warning("dlq_replay_failed", msg_id=msg_id, event_type=event_type)
                except Exception as e:
                    failed += 1
                    logger.error("dlq_replay_error", msg_id=msg_id, error=str(e))
        except Exception as e:
            logger.error("dlq_replay_cycle_error", error=str(e))
        return {"replayed": replayed, "failed": failed, "skipped": skipped}

    async def _dlq_replay_loop(self):
        await asyncio.sleep(settings.DLQ_REPLAY_INTERVAL)
        backoff = settings.DLQ_REPLAY_BACKOFF_BASE
        failures = 0
        while self.running:
            try:
                result = await self.replay_dlq(max_entries=settings.DLQ_REPLAY_MAX_ENTRIES)
                if result["replayed"] > 0 or result["failed"] > 0:
                    logger.info("dlq_replay_cycle", **result)
                if result["failed"] > 0:
                    failures += 1
                    backoff = min(backoff * 1.5, 3600)
                else:
                    failures = 0
                    backoff = settings.DLQ_REPLAY_BACKOFF_BASE
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("dlq_replay_loop_error", error=str(e))
            await asyncio.sleep(backoff)

    # ── Stats ────────────────────────────────────────────────

    @property
    def circuit_breaker_state(self) -> dict:
        return {
            "state": self._circuit_breaker.state.name,
            "total_opens": self._circuit_breaker.total_opens,
            "failure_rate": round(self._circuit_breaker.failure_rate, 4),
        }

    @property
    def stats(self):
        return {
            "events_processed": self._processed,
            "circuit_breaker": self.circuit_breaker_state,
            "persisted_count": self._persisted_count,
            "failed_count": self._failed_count,
            "retry_count": self._retry_count,
            "dlq_size": len(self._dlq),
            "events_by_type": dict(self._events_by_type),
            "persisted_by_type": dict(self._persisted_by_type),
            "dropped_by_type": dict(self._dropped_by_type),
            "duplicate_events_detected": self._duplicate_events_detected,
            "redis_dedup_hits": self._redis_dedup_hits,
            "redis_dedup_skipped": self._redis_dedup_skipped,
            "dlq_replayed": self._dlq_replayed,
            "dlq_replay_failures": self._dlq_replay_failures,
            "pending_claimed": self._pending_claimed,
            "pending_dlq_transferred": self._pending_dlq_transferred,
        }

    async def get_dlq(self) -> list[dict]:
        return list(self._dlq)

    async def clear_dlq(self) -> int:
        count = len(self._dlq)
        self._dlq.clear()
        try:
            from app.redis import get_redis
            r = await get_redis()
            await r.delete("market:data:dlq")
        except Exception as e:
            logger.error("dlq_clear_failed", error=str(e))
        return count


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
