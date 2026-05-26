import asyncio

from app.agents.base import BaseAgent
from app.core.events import EventBus
from app.core.logging import logger
from app.database import async_session_factory
from app.services.whale_service import WhaleService


class WhaleAgent(BaseAgent):
    name = "whale_agent"

    async def setup(self):
        logger.info("whale_agent_setup")

    async def loop(self):
        while self.running:
            try:
                r = await EventBus.subscribe_to_stream("market:data", "whale_agent", "whale_1")
                messages = await EventBus.read_stream(r, "market:data", "whale_agent", "whale_1", block=5000)

                for msg in messages:
                    data = msg.get("data", {})
                    event_type = msg.get("event_type", "")

                    if event_type in ("onchain_trade", "trade"):
                        wallet = data.get("from") or data.get("maker_address") or data.get("wallet")
                        if wallet:
                            async with async_session_factory() as db:
                                service = WhaleService(db)
                                wallet_obj = await service.upsert_wallet(wallet)
                                trade = await service.record_trade(
                                    wallet_address=wallet,
                                    market_id=None,
                                    outcome=data.get("outcome"),
                                    side=data.get("side", "buy"),
                                    size=float(data.get("value", data.get("size", 0)) or 0),
                                    price=float(data.get("price", 0) or 0),
                                    tx_hash=data.get("transaction_hash"),
                                )

                                scores = await service.get_wallet_scores(wallet, score_type="overall")
                                wallet_score = scores[0].score if scores else None
                                wallet_win_rate = float(wallet_obj.win_rate) if wallet_obj.win_rate else None

                                await EventBus.publish(
                                    "wallet:trade",
                                    "wallet.trade.detected",
                                    self.name,
                                    {
                                        "wallet": wallet,
                                        "trade_id": trade.id,
                                        "size": float(data.get("value", data.get("size", 0)) or 0),
                                        "event_type": event_type,
                                        "side": data.get("side", "buy"),
                                        "price": float(data.get("price", 0) or 0),
                                        "condition_id": data.get("condition_id", ""),
                                        "outcome": data.get("outcome"),
                                        "wallet_score": wallet_score,
                                        "wallet_win_rate": wallet_win_rate,
                                    },
                                )

                    await EventBus.ack_message(r, "market:data", "whale_agent", msg["id"])

            except Exception as e:
                logger.error("whale_agent_error", error=str(e))

            await asyncio.sleep(0.5)

    async def score_all_wallets(self):
        async with async_session_factory() as db:
            service = WhaleService(db)
            wallets = await service.list_wallets(limit=100)
            for wallet in wallets:
                await service.calculate_scores(wallet.address)
            logger.info("wallet_scores_calculated", count=len(wallets))
