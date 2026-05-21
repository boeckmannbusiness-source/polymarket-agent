import asyncio
from datetime import datetime, timezone

from app.agents.base import BaseAgent
from app.core.events import EventBus
from app.core.logging import logger


class ResearchAgent(BaseAgent):
    name = "research_agent"

    async def setup(self):
        logger.info("research_agent_setup")

    async def loop(self):
        while self.running:
            try:
                r = await EventBus.subscribe_to_stream("market:data", "research_agent", "research_1")
                messages = await EventBus.read_stream(r, "market:data", "research_agent", "research_1")

                for msg in messages:
                    await self.process_market_data(msg)
                    await EventBus.ack_message(r, "market:data", "research_agent", msg["id"])

            except Exception as e:
                logger.error("research_agent_error", error=str(e))

            await asyncio.sleep(1)

    async def process_market_data(self, msg: dict):
        event_type = msg.get("event_type", "unknown")
        data = msg.get("data", {})

        if event_type == "market_metadata":
            await self.log_event("market_discovered", {"slug": data.get("slug"), "title": data.get("title")})

        elif event_type == "last_trade_price":
            await self.log_event("trade_price", {"asset_id": data.get("asset_id"), "price": data.get("price")})
