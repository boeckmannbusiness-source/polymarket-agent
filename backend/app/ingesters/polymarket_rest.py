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
        logger.info("market_poller_started", interval=self.poll_interval)
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
                    data = response.json()
                    markets = data if isinstance(data, list) else data.get("data", [])
                    for market in markets:
                        await EventBus.publish(
                            "market:data",
                            "market_metadata",
                            self.name,
                            market,
                        )
                        await self._upsert_market(market)

                    logger.info("markets_polled", count=len(markets))

            except Exception as e:
                logger.error("market_poll_failed", error=str(e))

            await asyncio.sleep(self.poll_interval)

    async def _upsert_market(self, data: dict):
        from app.database import async_session_factory
        from app.services.market_service import MarketService

        condition_id = data.get("conditionId") or data.get("condition_id")
        if not condition_id:
            return

        title = data.get("question") or data.get("title")
        slug = data.get("slug")
        description = data.get("description")
        outcomes = data.get("outcomes")
        volume = data.get("volume")
        liquidity = data.get("liquidity")
        clob_token_ids = data.get("clobTokenIds") or data.get("clob_token_ids")

        start_date_str = data.get("startDate") or data.get("start_date")
        end_date_str = data.get("endDate") or data.get("end_date")
        start_date = _parse_ts(start_date_str) if start_date_str else None
        end_date = _parse_ts(end_date_str) if end_date_str else None

        resolved = data.get("closed", False)
        resolution = data.get("resolvedOutcome") or data.get("resolution")

        async with async_session_factory() as db:
            service = MarketService(db)
            try:
                await service.upsert_market(
                    condition_id,
                    slug=slug,
                    title=title,
                    description=description,
                    outcomes=outcomes,
                    start_date=start_date,
                    end_date=end_date,
                    volume=float(volume) if volume else None,
                    liquidity=float(liquidity) if liquidity else None,
                    clob_token_ids=clob_token_ids,
                    resolved=bool(resolved),
                    resolution=resolution,
                )
                await db.commit()
                logger.debug("market_upserted", condition_id=condition_id[:16])
            except Exception as e:
                logger.error("market_upsert_failed", condition_id=condition_id[:16], error=str(e))
                await db.rollback()

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


def _parse_ts(ts: str) -> Any:
    from datetime import datetime, timezone
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        try:
            return datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        except (ValueError, TypeError, OverflowError):
            return None


if __name__ == "__main__":
    ingester = PolymarketRESTIngester()
    asyncio.run(ingester.run())
