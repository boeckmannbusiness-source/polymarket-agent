import asyncio

from app.agents.base import BaseAgent
from app.core.events import EventBus
from app.core.logging import logger
from app.database import async_session_factory
from app.services.trade_service import TradeService
from app.schemas.trade import TradeCreateRequest


class ExecutionAgent(BaseAgent):
    name = "execution_agent"

    async def setup(self):
        logger.info("execution_agent_setup")

    async def loop(self):
        while self.running:
            try:
                r = await EventBus.subscribe_to_stream("trade:request", "execution_agent", "exec_1")
                messages = await EventBus.read_stream(r, "trade:request", "execution_agent", "exec_1", block=5000)

                for msg in messages:
                    data = msg.get("data", {})
                    event_type = msg.get("event_type", "")

                    if event_type == "trade.risk_approved":
                        await self.execute_trade(data)

                    await EventBus.ack_message(r, "trade:request", "execution_agent", msg["id"])

            except Exception as e:
                logger.error("execution_agent_error", error=str(e))

            await asyncio.sleep(0.5)

    async def execute_trade(self, data: dict):
        signal_id = data.get("signal_id")
        if not signal_id:
            return

        async with async_session_factory() as db:
            service = TradeService(db)
            request = TradeCreateRequest(
                market_id=None,
                signal_id=signal_id,
                side="buy",
                outcome="YES",
                size=100,
                reason=f"Auto-execution from signal {signal_id}",
                agent_id=self.name,
            )

            try:
                trade = await service.create_trade(request)
                await EventBus.publish(
                    "trade:execution",
                    "trade.executed",
                    self.name,
                    {
                        "trade_id": str(trade.id),
                        "status": trade.status,
                        "size": trade.size,
                        "price": float(trade.filled_price or 0),
                    },
                )
                await self.log_event("trade_executed", {"trade_id": str(trade.id), "status": trade.status})
            except Exception as e:
                await EventBus.publish(
                    "trade:execution",
                    "trade.failed",
                    self.name,
                    {"signal_id": signal_id, "error": str(e)},
                )
                await self.log_event("trade_failed", {"signal_id": signal_id, "error": str(e)})
