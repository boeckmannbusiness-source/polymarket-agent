import asyncio

from app.agents.base import BaseAgent
from app.core.events import EventBus
from app.core.logging import logger
from app.database import async_session_factory
from app.llm import get_llm_provider
from app.services.signal_service import SignalService
from app.services.strategy_service import StrategyService
from app.strategies import get_strategy, get_strategy_names


class SignalAgent(BaseAgent):
    name = "signal_agent"

    def __init__(self):
        super().__init__()
        self.llm = get_llm_provider()

    async def setup(self):
        names = get_strategy_names()
        logger.info("signal_agent_setup", strategies=names, llm_provider=self.llm.provider_name)

    async def loop(self):
        while self.running:
            try:
                r = await EventBus.subscribe_to_stream("wallet:trade", "signal_agent", "signal_1")
                messages = await EventBus.read_stream(r, "wallet:trade", "signal_agent", "signal_1", block=10000)

                for msg in messages:
                    data = msg.get("data", {})

                    async with async_session_factory() as db:
                        strategy_service = StrategyService(db)
                        signal_service = SignalService(db)

                        for strategy_name in get_strategy_names():
                            config_row = await strategy_service.get_config(strategy_name)
                            config = config_row.config if config_row else None

                            try:
                                strategy = get_strategy(strategy_name, config=config)
                                if not strategy.config.enabled:
                                    continue

                                signal = await strategy.generate_signal(data)
                                if signal is None:
                                    continue

                                created = await signal_service.create_signal(
                                    market_id=signal.market_id,
                                    signal_type=strategy_name,
                                    direction="bullish" if signal.signal == "BUY_YES" else "bearish" if signal.signal == "BUY_NO" else "neutral",
                                    confidence=signal.confidence,
                                    reasoning=signal.reason,
                                    source_agent=f"{strategy_name}:{signal.strategy_version}",
                                    source_data={
                                        "risk_score": signal.risk_score,
                                        "time_horizon": signal.time_horizon,
                                        "market_regime": signal.market_regime,
                                        "strategy_version": signal.strategy_version,
                                        "feature_values": signal.feature_values,
                                    },
                                    ttl_minutes=60,
                                )

                                await EventBus.publish(
                                    "signal:generated",
                                    "signal.generated",
                                    self.name,
                                    {
                                        "signal_id": str(created.id),
                                        "strategy": strategy_name,
                                        "signal": signal.signal,
                                        "confidence": signal.confidence,
                                        "reasoning": signal.reason[:200],
                                        "risk_score": signal.risk_score,
                                    },
                                )
                                await self.log_event("signal_generated", {
                                    "strategy": strategy_name,
                                    "signal_id": str(created.id),
                                    "signal": signal.signal,
                                    "confidence": signal.confidence,
                                })

                            except Exception as e:
                                logger.error("strategy_error", strategy=strategy_name, error=str(e))

                        await db.commit()

                    await EventBus.ack_message(r, "wallet:trade", "signal_agent", msg["id"])

            except Exception as e:
                logger.error("signal_agent_error", error=str(e))

            await asyncio.sleep(0.5)
