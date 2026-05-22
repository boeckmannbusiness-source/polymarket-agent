import asyncio
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

    async def connect(self):
        self.ws = await websockets.connect(settings.POLYMARKET_WS_URL)
        logger.info("ws_connected", url=settings.POLYMARKET_WS_URL)

        await self._refresh_mappings()
        sub_ids = self._get_asset_ids()
        self._subscribed_assets = sub_ids

        if sub_ids:
            chunk_size = 200
            for i in range(0, len(sub_ids), chunk_size):
                chunk = sub_ids[i : i + chunk_size]
                subscribe_msg = {
                    "type": "market",
                    "assets_ids": chunk,
                }
                await self.ws.send(json.dumps(subscribe_msg))
            logger.info("ws_subscribed", asset_count=len(sub_ids), chunks=(len(sub_ids) + chunk_size - 1) // chunk_size)
        else:
            logger.warning("ws_no_assets_to_subscribe")

    async def run(self):
        self.running = True
        logger.info("ws_ingester_started")
        try:
            await self.connect()
        except Exception as e:
            logger.error("ws_connect_failed", error=str(e), will_retry=True)
        self._tasks.append(asyncio.create_task(self._heartbeat()))
        self._tasks.append(asyncio.create_task(self._subscription_refresher()))
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
                        msg = {"type": "market", "assets_ids": chunk}
                        await self.ws.send(json.dumps(msg))
                    self._subscribed_assets.extend(new_ids)
                    logger.info("ws_subscribed_new_assets", count=len(new_ids))
                stale_count = len(self._subscribed_assets) - len(current_ids)
                if stale_count > 0:
                    self._subscribed_assets = current_ids
                    logger.info("ws_pruned_stale_assets", count=stale_count)
            except Exception as e:
                logger.error("ws_subscription_refresh_failed", error=str(e))
            await asyncio.sleep(300)

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

                event_type = data.get("event_type", "unknown")

                if event_type == "last_trade_price":
                    asset_id = data.get("asset_id")
                    condition_id = self._asset_to_condition.get(asset_id) if asset_id else None
                    enriched = {
                        **data,
                        "condition_id": condition_id,
                        "conditionId": condition_id,
                    }
                    await EventBus.publish(
                        "market:data",
                        "trade",
                        self.name,
                        enriched,
                    )
                elif event_type == "book":
                    await EventBus.publish(
                        "market:data",
                        "orderbook_snapshot",
                        self.name,
                        data,
                    )
                elif event_type == "price_change":
                    await EventBus.publish(
                        "market:data",
                        "price_change",
                        self.name,
                        data,
                    )

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
            msg = {"operation": "subscribe", "assets_ids": asset_ids}
            await self.ws.send(json.dumps(msg))
            self._subscribed_assets.extend(asset_ids)
            logger.info("subscribed_assets", count=len(asset_ids))

    async def unsubscribe_assets(self, asset_ids: list[str]):
        if self.ws:
            msg = {"operation": "unsubscribe", "assets_ids": asset_ids}
            await self.ws.send(json.dumps(msg))
            self._subscribed_assets = [a for a in self._subscribed_assets if a not in asset_ids]

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
        }


if __name__ == "__main__":
    ingester = PolymarketWSIngester()
    asyncio.run(ingester.run())
