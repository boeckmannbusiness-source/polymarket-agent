import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import websockets

from app.config import settings
from app.core.logging import logger
from app.ingesters.base import BaseIngester
from app.core.events import EventBus
from app.database import async_session_factory
from sqlalchemy import select
from app.models import Market

_REQUIRED_FIELDS = {"condition_id", "asset_id", "timestamp"}
_OPTIONAL_FIELDS = {"price", "size", "wallet", "side", "outcome"}


class PolymarketWSIngester(BaseIngester):
    name = "polymarket_ws"

    def __init__(self, asset_ids: list[str] | None = None):
        super().__init__()
        self.asset_ids: list[str] = asset_ids or []
        self.ws = None
        self._tasks: list[asyncio.Task] = []

        self._messages_received = 0
        self._last_message_time: datetime | None = None
        self._reconnect_count = 0
        self._subscribed_assets: list[str] = []

        self._asset_to_condition: dict[str, str] = {}
        self._condition_to_asset: dict[str, list[str]] = {}

        # Event classification counters
        self._events_by_type: dict[str, int] = {}
        self._normalized_by_type: dict[str, int] = {}
        self._validation_failures = 0
        self._unknown_by_type: dict[str, int] = {}
        self._dropped_by_type: dict[str, int] = {}

        # Duplicate detection (in-memory LRU)
        self._recent_hashes: set[str] = set()
        self._recent_hash_order: list[str] = []
        self._max_hash_cache = 1000
        self._duplicate_events_detected = 0

        # Raw event buffer (last 50)
        self._last_raw_events: list[dict] = []
        self._max_raw_events = 50

        # Live trace buffer (last 200, 1h TTL)
        self._live_traces: dict[str, dict] = {}
        self._max_live_traces = 200

        # Counting
        self._normalized_events_published = 0
        self._parsed_events = 0
        self._parse_failures = 0

    # ── Refresh / subscriptions ──────────────────────────────

    async def _refresh_mappings(self):
        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    select(Market.condition_id, Market.clob_token_ids, Market.resolved)
                    .where(Market.resolved == False)
                    .where(Market.clob_token_ids.isnot(None))
                )
                rows = result.all()
            new_asset_to_condition = {}
            new_condition_to_asset = {}
            for condition_id, token_ids, _ in rows:
                if not token_ids:
                    continue
                ids = [t for t in token_ids if t]
                new_condition_to_asset[condition_id] = ids
                for tid in ids:
                    new_asset_to_condition[tid] = condition_id
            self._asset_to_condition = new_asset_to_condition
            self._condition_to_asset = new_condition_to_asset
            logger.info(
                "ws_mappings_refreshed",
                conditions=len(new_condition_to_asset),
                assets=len(new_asset_to_condition),
            )
        except Exception as e:
            logger.error("ws_mappings_refresh_failed", error=str(e))

    def _get_asset_ids(self) -> list[str]:
        all_ids = []
        for ids in self._condition_to_asset.values():
            all_ids.extend(ids)
        return all_ids

    async def _try_subscribe(self, sub_format: dict) -> bool:
        try:
            await self.ws.send(json.dumps(sub_format))
            return True
        except Exception as e:
            logger.warning("ws_subscribe_attempt_failed", format=sub_format.get("type"), error=str(e))
            return False

    async def connect(self):
        self.ws = await websockets.connect(settings.POLYMARKET_WS_URL)
        logger.info("ws_connected", url=settings.POLYMARKET_WS_URL)

        # Clear reconnect-sensitive buffers
        self._last_raw_events.clear()
        self._live_traces.clear()

        await self._refresh_mappings()
        sub_ids = self._get_asset_ids()
        self._subscribed_assets = sub_ids

        if sub_ids:
            chunk_size = 200
            for i in range(0, len(sub_ids), chunk_size):
                chunk = sub_ids[i : i + chunk_size]
                sub_formats = [
                    {"type": "market", "assets_ids": chunk},
                ]
                success = False
                for fmt in sub_formats:
                    if await self._try_subscribe(fmt):
                        success = True
                        break
                if not success:
                    logger.error("ws_subscribe_all_formats_failed", chunk_index=i // chunk_size)
            logger.info("ws_subscribed", asset_count=len(sub_ids))
        else:
            logger.warning("ws_no_assets_to_subscribe")

    # ── Lifecycle ────────────────────────────────────────────

    async def run(self):
        self.running = True
        logger.info("ws_ingester_started")
        try:
            await self.connect()
        except Exception as e:
            logger.error("ws_connect_failed", error=str(e), will_retry=True)
        self._tasks.append(asyncio.create_task(self._heartbeat()))
        self._tasks.append(asyncio.create_task(self._subscription_refresher()))
        self._tasks.append(asyncio.create_task(self._cleanup_loop()))
        await self._message_loop()

    async def stop(self):
        self.running = False
        for task in self._tasks:
            task.cancel()
        if self.ws:
            await self.ws.close()

    async def _heartbeat(self):
        while self.running:
            try:
                if self.ws and getattr(self.ws, 'close_code', None) is None:
                    await self.ws.ping()
                await asyncio.sleep(30)
            except Exception as e:
                logger.error("heartbeat_failed", error=str(e))
                await asyncio.sleep(5)

    async def _subscription_refresher(self):
        await asyncio.sleep(300)
        while self.running:
            try:
                await self._refresh_mappings()
                current_ids = self._get_asset_ids()
                new_ids = [aid for aid in current_ids if aid not in self._subscribed_assets]
                if new_ids:
                    chunk_size = 200
                    for i in range(0, len(new_ids), chunk_size):
                        chunk = new_ids[i : i + chunk_size]
                        for fmt in [{"type": "market", "assets_ids": chunk}]:
                            await self._try_subscribe(fmt)
                    self._subscribed_assets.extend(new_ids)
                    logger.info("ws_subscribed_new_assets", count=len(new_ids))
                stale_count = len(self._subscribed_assets) - len(current_ids)
                if stale_count > 0:
                    self._subscribed_assets = current_ids
                    logger.info("ws_pruned_stale_assets", count=stale_count)
            except Exception as e:
                logger.error("ws_subscription_refresh_failed", error=str(e))
            await asyncio.sleep(300)

    async def _cleanup_loop(self):
        while self.running:
            await asyncio.sleep(300)
            self._prune_stale_traces()

    # ── Validation & dedup ───────────────────────────────────

    @staticmethod
    def _compute_event_hash(event: dict) -> str:
        raw = (
            str(event.get("event_type", "")),
            str(event.get("condition_id", "")),
            str(event.get("asset_id", "")),
            str(event.get("price", "")),
            str(event.get("size", "")),
            str(event.get("timestamp", "")),
            str(event.get("wallet", "")),
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

    @staticmethod
    def _validate_normalized(event: dict) -> tuple[bool, str]:
        missing = _REQUIRED_FIELDS - set(event.keys())
        if missing:
            return False, f"missing_fields:{','.join(sorted(missing))}"
        if not event.get("condition_id"):
            return False, "empty_condition_id"
        if not event.get("asset_id"):
            return False, "empty_asset_id"
        if not event.get("timestamp"):
            return False, "empty_timestamp"
        return True, ""

    # ── Normalization ────────────────────────────────────────

    def _normalize_trade_event(self, raw: dict, event_type: str) -> dict | None:
        asset_id = raw.get("asset_id") or raw.get("assetId")
        if not asset_id:
            return None
        condition_id = self._asset_to_condition.get(asset_id)
        return {
            "event_type": "trade",
            "market_id": None,
            "condition_id": condition_id,
            "conditionId": condition_id,
            "asset_id": asset_id,
            "price": _safe_float(raw.get("price")),
            "size": _safe_float(raw.get("size")),
            "timestamp": raw.get("timestamp") or raw.get("t"),
            "wallet": raw.get("maker") or raw.get("wallet") or raw.get("user"),
            "side": raw.get("side"),
            "outcome": raw.get("outcome"),
            "type": event_type,
            "raw_type": event_type,
        }

    def _normalize_price_event(self, raw: dict) -> dict | None:
        asset_id = raw.get("asset_id") or raw.get("assetId")
        if not asset_id:
            return None
        condition_id = self._asset_to_condition.get(asset_id)
        price = None
        for key in ["price", "marketPrice", "lastPrice", "close"]:
            val = raw.get(key)
            if val is not None:
                price = _safe_float(val)
                break
        return {
            "event_type": "price_change",
            "market_id": None,
            "condition_id": condition_id,
            "conditionId": condition_id,
            "asset_id": asset_id,
            "price": price,
            "timestamp": raw.get("timestamp") or raw.get("t"),
        }

    # ── Store raw events ─────────────────────────────────────

    def _store_raw_event(self, raw: dict, event_type_raw: str, success: bool, note: str = ""):
        self._last_raw_events.append({
            "event_type": event_type_raw,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "parsing_success": success,
            "note": note,
            "sample_keys": list(raw.keys())[:10],
            "sample_values": {k: str(raw[k])[:80] for k in list(raw.keys())[:5]},
        })
        if len(self._last_raw_events) > self._max_raw_events:
            self._last_raw_events = self._last_raw_events[-self._max_raw_events:]

    # ── Publish normalized event with full validation ────────

    async def _publish_normalized(self, normalized: dict, event_type: str):
        valid, reason = self._validate_normalized(normalized)
        if not valid:
            self._validation_failures += 1
            self._dropped_by_type[event_type] = self._dropped_by_type.get(event_type, 0) + 1
            self._store_raw_event(normalized, event_type, False, f"validation_failed:{reason}")
            return

        event_hash = self._compute_event_hash(normalized)
        if self._is_duplicate(event_hash):
            self._dropped_by_type[event_type] = self._dropped_by_type.get(event_type, 0) + 1
            self._store_raw_event(normalized, event_type, False, f"duplicate_hash:{event_hash[:12]}")
            return

        self._normalized_by_type[event_type] = self._normalized_by_type.get(event_type, 0) + 1

        trace_id = f"{event_type}_{datetime.now(timezone.utc).timestamp()}"
        normalized["_trace_id"] = trace_id
        normalized["_normalized_at"] = datetime.now(timezone.utc).isoformat()
        self._live_traces[trace_id] = normalized
        if len(self._live_traces) > self._max_live_traces:
            self._prune_stale_traces()

        await EventBus.publish("market:data", event_type, self.name, normalized)
        self._normalized_events_published += 1

    def _prune_stale_traces(self):
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - 3600
        stale = [k for k, v in self._live_traces.items()
                 if isinstance(v.get("_normalized_at"), str)
                 and _parse_ts(v["_normalized_at"]) < cutoff]
        for k in stale:
            del self._live_traces[k]
        over = len(self._live_traces) - self._max_live_traces
        if over > 0:
            keys = list(self._live_traces.keys())
            for k in keys[:over]:
                del self._live_traces[k]

    # ── Message loop ─────────────────────────────────────────

    async def _message_loop(self):
        while self.running:
            try:
                if self.ws is None or getattr(self.ws, 'close_code', None) is not None:
                    self._reconnect_count += 1
                    logger.warning("ws_not_connected, reconnecting...", reconnect=self._reconnect_count)
                    await asyncio.sleep(5)
                    try:
                        await self.connect()
                    except Exception as e:
                        logger.error("ws_reconnect_failed", error=str(e))
                    await asyncio.sleep(1)
                    continue

                message = await self.ws.recv()
                self._messages_received += 1
                self._last_message_time = datetime.now(timezone.utc)
                data = json.loads(message)

                event_type = data.get("type") or data.get("event_type") or data.get("channel") or "unknown"
                self._events_by_type[event_type] = self._events_by_type.get(event_type, 0) + 1

                if self._events_by_type[event_type] <= 3:
                    logger.info("ws_new_event_type", type=event_type, sample_keys=list(data.keys())[:10], full_sample=str(data)[:300])

                if event_type == "last_trade_price":
                    self._parsed_events += 1
                    self._store_raw_event(data, event_type, True, "parsed as trade")
                    normalized = self._normalize_trade_event(data, event_type)
                    if normalized:
                        await self._publish_normalized(normalized, "trade")
                    else:
                        self._parse_failures += 1
                        self._store_raw_event(data, event_type, False, "normalization_failed")
                        await EventBus.publish("market:data", "trade", self.name, data)

                elif event_type == "price_change":
                    self._parsed_events += 1
                    self._store_raw_event(data, event_type, True, "parsed as price_change")
                    normalized = self._normalize_price_event(data)
                    if normalized:
                        await self._publish_normalized(normalized, "price_change")

                elif event_type == "book":
                    self._store_raw_event(data, event_type, True, "parsed as orderbook")
                    await EventBus.publish("market:data", "orderbook_snapshot", self.name, data)

                elif event_type in ("subscription", "subscribe", "ack", "error"):
                    self._store_raw_event(data, event_type, True, f"system_message:{event_type}")
                    logger.info("ws_system_msg", type=event_type, data=str(data)[:200])

                else:
                    self._store_raw_event(data, event_type, True, "unhandled_type")
                    self._unknown_by_type[event_type] = self._unknown_by_type.get(event_type, 0) + 1
                    await EventBus.publish("market:data", event_type, self.name, data)

            except websockets.ConnectionClosed:
                self._reconnect_count += 1
                logger.warning("ws_disconnected, reconnecting...", reconnect=self._reconnect_count)
                await asyncio.sleep(5)
                try:
                    await self.connect()
                except Exception as e:
                    logger.error("ws_reconnect_failed", error=str(e))
            except Exception as e:
                logger.error("ws_error", error=str(e))
                await asyncio.sleep(1)

    async def subscribe_assets(self, asset_ids: list[str]):
        if self.ws:
            for fmt in [{"type": "market", "assets_ids": asset_ids}]:
                await self._try_subscribe(fmt)
            self._subscribed_assets.extend(asset_ids)
            logger.info("subscribed_assets", count=len(asset_ids))

    async def unsubscribe_assets(self, asset_ids: list[str]):
        if self.ws:
            msg = {"operation": "unsubscribe", "assets_ids": asset_ids}
            await self.ws.send(json.dumps(msg))
            self._subscribed_assets = [a for a in self._subscribed_assets if a not in asset_ids]

    # ── Properties ───────────────────────────────────────────

    @property
    def stats(self) -> dict:
        connected = False
        if self.ws is not None:
            try:
                connected = not self.ws.close_code
            except Exception:
                connected = False
        return {
            "connected": connected,
            "subscribed_assets": len(self._subscribed_assets),
            "mapped_conditions": len(self._condition_to_asset),
            "mapped_assets": len(self._asset_to_condition),
            "messages_received": self._messages_received,
            "last_message_time": self._last_message_time.isoformat() if self._last_message_time else None,
            "reconnect_count": self._reconnect_count,
            "event_type_counts": dict(self._events_by_type),
            "parsed_events": self._parsed_events,
            "parse_failures": self._parse_failures,
            "normalized_events_published": self._normalized_events_published,
        }

    @property
    def last_raw_events(self) -> list[dict]:
        return list(self._last_raw_events)

    @property
    def live_pipeline(self) -> dict:
        return {
            "ws": self.stats,
            "event_classification": {
                "events_by_type": dict(self._events_by_type),
                "normalized_by_type": dict(self._normalized_by_type),
                "unknown_by_type": dict(self._unknown_by_type),
                "dropped_by_type": dict(self._dropped_by_type),
                "validation_failures": self._validation_failures,
                "duplicate_events_detected": self._duplicate_events_detected,
            },
            "recent_events_sample": self._last_raw_events[-5:] if self._last_raw_events else [],
            "trace_count": len(self._live_traces),
        }

    @property
    def live_traces(self) -> dict[str, dict]:
        return dict(self._live_traces)

    @property
    def event_stats(self) -> dict:
        return {
            "events_by_type": dict(self._events_by_type),
            "normalized_by_type": dict(self._normalized_by_type),
            "unknown_by_type": dict(self._unknown_by_type),
            "dropped_by_type": dict(self._dropped_by_type),
            "validation_failures": self._validation_failures,
            "duplicate_events_detected": self._duplicate_events_detected,
            "total_messages": self._messages_received,
            "total_normalized": sum(self._normalized_by_type.values()),
            "total_dropped": sum(self._dropped_by_type.values()),
        }


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _parse_ts(iso_str: str) -> float:
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return 0


if __name__ == "__main__":
    ingester = PolymarketWSIngester()
    asyncio.run(ingester.run())
