import asyncio
from typing import Any

import httpx

from app.config import settings
from app.core.logging import logger
from app.ingesters.base import BaseIngester
from app.core.events import EventBus


class PolymarketRESTIngester(BaseIngester):
    name = "polymarket_rest"

    def __init__(self, poll_interval: int = 60):
        super().__init__()
        self.poll_interval = poll_interval
        self.client = httpx.AsyncClient(timeout=30.0)
        self._tasks: list[asyncio.Task] = []

    async def run(self):
        self.running = True
        self._tasks.append(asyncio.create_task(self._poll_markets()))
        self._tasks.append(asyncio.create_task(self._poll_leaderboard()))

        await asyncio.gather(*self._tasks)

    async def stop(self):
        self.running = False
        for task in self._tasks:
            task.cancel()
        await self.client.aclose()

    async def _poll_markets(self):
        while self.running:
            try:
                params = {
                    "limit": 100,
                    "closed": False,
                    "order": "volume",
                    "ascending": "false",
                }
                response = await self.client.get(
                    f"{settings.POLYMARKET_GAMMA_API_URL}/markets",
                    params=params,
                )
                if response.status_code == 200:
                    markets = response.json()
                    for market in markets:
                        await EventBus.publish(
                            "market:data",
                            "market_metadata",
                            self.name,
                            market,
                        )

                    logger.info("markets_polled", count=len(markets))

            except Exception as e:
                logger.error("market_poll_failed", error=str(e))

            await asyncio.sleep(self.poll_interval)

    async def _poll_leaderboard(self):
        await asyncio.sleep(30)
        while self.running:
            try:
                response = await self.client.get(
                    f"{settings.POLYMARKET_DATA_API_URL}/leaderboard",
                    params={"limit": 50},
                )
                if response.status_code == 200:
                    traders = response.json()
                    await EventBus.publish(
                        "market:data",
                        "leaderboard_snapshot",
                        self.name,
                        {"traders": traders, "timestamp": asyncio.get_event_loop().time()},
                    )
                    logger.info("leaderboard_polled", count=len(traders))

            except Exception as e:
                logger.error("leaderboard_poll_failed", error=str(e))

            await asyncio.sleep(300)

    async def fetch_market_by_slug(self, slug: str) -> dict[str, Any] | None:
        try:
            response = await self.client.get(
                f"{settings.POLYMARKET_GAMMA_API_URL}/markets/slug/{slug}"
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error("fetch_market_failed", slug=slug, error=str(e))
        return None

    async def fetch_wallet_trades(self, wallet_address: str, limit: int = 100) -> list[dict]:
        try:
            response = await self.client.get(
                f"{settings.POLYMARKET_DATA_API_URL}/trades",
                params={"user": wallet_address, "limit": limit},
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error("fetch_wallet_trades_failed", wallet=wallet_address[:8], error=str(e))
        return []


if __name__ == "__main__":
    ingester = PolymarketRESTIngester()
    asyncio.run(ingester.run())
