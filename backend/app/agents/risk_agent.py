import asyncio
from datetime import datetime, timezone

from app.agents.base import BaseAgent
from app.core.events import EventBus
from app.core.logging import logger
from app.database import async_session_factory
from app.services.risk_service import RiskService


class RiskAgent(BaseAgent):
    name = "risk_agent"

    async def setup(self):
        logger.info("risk_agent_setup")

    async def loop(self):
        while self.running:
            try:
                r = await EventBus.subscribe_to_stream("signal:generated", "risk_agent", "risk_1")
                messages = await EventBus.read_stream(r, "signal:generated", "risk_agent", "risk_1", block=10000)

                for msg in messages:
                    await self.evaluate_signal(msg)
                    await EventBus.ack_message(r, "signal:generated", "risk_agent", msg["id"])

            except Exception as e:
                logger.error("risk_agent_error", error=str(e))

            await asyncio.sleep(0.5)

    async def evaluate_signal(self, msg: dict):
        data = msg.get("data", {})
        confidence = data.get("confidence", 0.5)
        signal_id = data.get("signal_id")

        async with async_session_factory() as db:
            risk_service = RiskService(db)
            check = await risk_service.validate_trade(
                market_id=None,
                side="buy",
                size=100,
                confidence=confidence,
                agent_id=self.name,
            )

            if check.approved:
                await EventBus.publish(
                    "trade:request",
                    "trade.risk_approved",
                    self.name,
                    {"signal_id": signal_id, "confidence": confidence, "risk_check": str(check)},
                )
                await self.log_event("risk_approved", {"signal_id": signal_id, "confidence": confidence})
            else:
                await EventBus.publish(
                    "trade:request",
                    "trade.risk_rejected",
                    self.name,
                    {"signal_id": signal_id, "reason": check.reason},
                )
                await self.log_event("risk_rejected", {"signal_id": signal_id, "reason": check.reason})
