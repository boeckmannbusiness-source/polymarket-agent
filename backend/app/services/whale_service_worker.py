"""Standalone worker for wallet tracking and scoring."""
import asyncio

import httpx

from app.config import settings
from app.core.events import EventBus
from app.core.logging import logger
from app.database import async_session_factory
from app.services.whale_service import WhaleService


class WhaleTrackerWorker:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.running = False

    async def run(self):
        self.running = True
        logger.info("whale_tracker_started")

        while self.running:
            try:
                await self.poll_leaderboard()
                await self.score_top_wallets()
            except Exception as e:
                logger.error("whale_tracker_error", error=str(e))

            await asyncio.sleep(300)

    async def stop(self):
        self.running = False
        await self.client.aclose()

    async def poll_leaderboard(self):
        try:
            response = await self.client.get(
                f"{settings.POLYMARKET_DATA_API_URL}/leaderboard",
                params={"limit": 100},
            )
            if response.status_code != 200:
                return

            traders = response.json()
            async with async_session_factory() as db:
                service = WhaleService(db)
                for trader in traders[:50]:
                    address = trader.get("address", trader.get("trader", ""))
                    if address:
                        await service.upsert_wallet(
                            address,
                            total_trades=trader.get("total_trades", 0),
                            total_volume=float(trader.get("total_volume", 0)),
                            realized_pnl=float(trader.get("realized_pnl", 0)),
                        )

            logger.info("leaderboard_processed", count=min(len(traders), 50))

        except Exception as e:
            logger.error("leaderboard_poll_failed", error=str(e))

    async def score_top_wallets(self):
        async with async_session_factory() as db:
            service = WhaleService(db)
            wallets = await service.list_wallets(limit=50)
            for wallet in wallets:
                await service.calculate_scores(wallet.address)
            logger.info("wallet_scoring_complete", count=len(wallets))


if __name__ == "__main__":
    worker = WhaleTrackerWorker()

    async def main():
        await worker.run()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(worker.stop())
