import asyncio
import json
from typing import Any

import websockets

from app.config import settings
from app.core.logging import logger
from app.ingesters.base import BaseIngester
from app.core.events import EventBus


class PolymarketWSIngester(BaseIngester):
    name = "polymarket_ws"

    def __init__(self, asset_ids: list[str] | None = None):
        super().__init__()
        self.asset_ids = asset_ids or []
        self.ws = None
        self._tasks: list[asyncio.Task] = []

    async def connect(self):
        self.ws = await websockets.connect(settings.POLYMARKET_WS_URL)
        logger.info("ws_connected", url=settings.POLYMARKET_WS_URL)

        if self.asset_ids:
            subscribe_msg = {
                "type": "market",
                "assets_ids": self.asset_ids,
                "initial_dump": True,
                "level": 2,
                "custom_feature_enabled": False,
            }
            await self.ws.send(json.dumps(subscribe_msg))
            logger.info("ws_subscribed", asset_count=len(self.asset_ids))

    async def run(self):
        self.running = True
        logger.info("ws_ingester_started")
        try:
            await self.connect()
        except Exception as e:
            logger.error("ws_connect_failed", error=str(e), will_retry=True)
        self._tasks.append(asyncio.create_task(self._heartbeat()))
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
                if self.ws:
                    await self.ws.send("PING")
                await asyncio.sleep(10)
            except Exception as e:
                logger.error("heartbeat_failed", error=str(e))
                break

    async def _message_loop(self):
        while self.running:
            try:
                message = await self.ws.recv()
                data = json.loads(message)

                event_type = data.get("event_type", "unknown")

                await self.publish_event(event_type, data)

                if event_type == "last_trade_price":
                    await EventBus.publish(
                        "market:data",
                        "trade",
                        self.name,
                        {
                            "asset_id": data.get("asset_id"),
                            "price": data.get("price"),
                            "side": data.get("side"),
                            "size": data.get("size"),
                            "timestamp": data.get("timestamp"),
                        },
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
                logger.warning("ws_disconnected, reconnecting...")
                await asyncio.sleep(5)
                await self.connect()
            except Exception as e:
                logger.error("ws_error", error=str(e))
                await asyncio.sleep(1)

    async def subscribe_assets(self, asset_ids: list[str]):
        if self.ws:
            msg = {"operation": "subscribe", "assets_ids": asset_ids}
            await self.ws.send(json.dumps(msg))
            self.asset_ids.extend(asset_ids)
            logger.info("subscribed_assets", count=len(asset_ids))

    async def unsubscribe_assets(self, asset_ids: list[str]):
        if self.ws:
            msg = {"operation": "unsubscribe", "assets_ids": asset_ids}
            await self.ws.send(json.dumps(msg))
            self.asset_ids = [a for a in self.asset_ids if a not in asset_ids]


if __name__ == "__main__":
    ingester = PolymarketWSIngester()
    asyncio.run(ingester.run())
