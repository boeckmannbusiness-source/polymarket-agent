import asyncio
import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.core.events import EventBus
from app.core.logging import logger
from app.database import async_session_factory
from app.llm import get_llm_provider
from app.services.signal_service import SignalService
from app.services.market_service import MarketService


class SignalOutput(BaseModel):
    market_condition_id: str | None = Field(None, description="The condition_id of the market")
    direction: str = Field(..., pattern="^(bullish|bearish|neutral)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    signal_type: str = Field(..., pattern="^(momentum|whale_behavior|anomaly|sentiment|cross_market)$")
    implied_probability: float | None = Field(None, ge=0.0, le=1.0)
    estimated_probability: float | None = Field(None, ge=0.0, le=1.0)
    reasoning: str = Field(..., min_length=1)
    ttl_minutes: int = Field(default=60, ge=5, le=1440)


class SignalAgent(BaseAgent):
    name = "signal_agent"

    def __init__(self):
        super().__init__()
        self.llm = get_llm_provider()

    async def setup(self):
        logger.info("signal_agent_setup", llm_provider=self.llm.provider_name)

    async def loop(self):
        while self.running:
            try:
                r = await EventBus.subscribe_to_stream("wallet:trade", "signal_agent", "signal_1")
                messages = await EventBus.read_stream(r, "wallet:trade", "signal_agent", "signal_1", block=10000)

                for msg in messages:
                    data = msg.get("data", {})
                    wallet = data.get("wallet")
                    size = data.get("size", 0)

                    if size and float(size) > 1000:
                        signal = await self.generate_signal_from_whale(wallet, data)
                        if signal:
                            async with async_session_factory() as db:
                                service = SignalService(db)
                                created = await service.create_signal(
                                    market_id=None,
                                    signal_type=signal.signal_type,
                                    direction=signal.direction,
                                    confidence=signal.confidence,
                                    implied_probability=signal.implied_probability,
                                    estimated_probability=signal.estimated_probability,
                                    reasoning=signal.reasoning,
                                    source_agent=self.name,
                                    source_data={"wallet": wallet, "trade_size": size},
                                    ttl_minutes=signal.ttl_minutes,
                                )
                                await EventBus.publish(
                                    "signal:generated",
                                    "signal.generated",
                                    self.name,
                                    {
                                        "signal_id": str(created.id),
                                        "direction": signal.direction,
                                        "confidence": signal.confidence,
                                        "reasoning": signal.reasoning[:200],
                                    },
                                )
                                await self.log_event("signal_generated", {
                                    "signal_id": str(created.id),
                                    "direction": signal.direction,
                                    "confidence": signal.confidence,
                                })

                    await EventBus.ack_message(r, "wallet:trade", "signal_agent", msg["id"])

            except Exception as e:
                logger.error("signal_agent_error", error=str(e))

            await asyncio.sleep(0.5)

    async def generate_signal_from_whale(self, wallet: str, trade_data: dict) -> SignalOutput | None:
        try:
            prompt = (
                f"A whale wallet {wallet[:8]}... just executed a trade of size {trade_data.get('size', 'unknown')}.\n"
                f"Trade type: {trade_data.get('event_type', 'unknown')}\n"
                f"Analyze whether this is a signal worth following and output a structured assessment."
            )
            system = (
                "You are a prediction market signal analyst. Given a whale trade, determine:\n"
                "1. Whether this is a signal worth following (confidence)\n"
                "2. What direction it suggests\n"
                "3. What type of signal this is\n"
                "Respond with the exact JSON schema provided."
            )

            result = await self.llm.generate_structured(prompt, SignalOutput, system=system, temperature=0.1)
            return result

        except Exception as e:
            logger.error("signal_generation_failed", wallet=wallet[:8], error=str(e))
            return SignalOutput(
                direction="neutral",
                confidence=0.5,
                signal_type="momentum",
                reasoning=f"Whale trade detected from {wallet[:8]} but analysis failed: {str(e)[:100]}",
            )
