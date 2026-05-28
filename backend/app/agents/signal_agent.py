import asyncio
import uuid

from app.agents.base import BaseAgent
from app.core.events import EventBus
from app.core.logging import logger
from app.database import async_session_factory
from app.services.market_enrichment_service import MarketEnrichmentService
from app.services.signal_service import SignalService
from app.services.strategy_service import StrategyService
from app.strategies import get_strategy, get_strategy_names
from app.models import Signal


class SignalAgent(BaseAgent):
    name = "signal_agent"

    async def setup(self):
        names = get_strategy_names()
        logger.info("signal_agent_setup", strategies=names)

    async def loop(self):
        while self.running:
            try:
                r = await EventBus.subscribe_to_stream("wallet:trade", "signal_agent", "signal_1")
                messages = await EventBus.read_stream(r, "wallet:trade", "signal_agent", "signal_1", block=10000)

                for msg in messages:
                    data = dict(msg.get("data", {}))

                    async with async_session_factory() as db:
                        enrichment = await MarketEnrichmentService(db).enrich(
                            data.get("condition_id") or data.get("market_condition_id")
                        )
                        data.update(enrichment)

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

                                side = data.get("side", "buy")
                                outcome = data.get("outcome", "YES")
                                size = float(data.get("size", data.get("value", 100)) or 100)

                                from uuid import UUID as _UUID
                                try:
                                    market_uuid = _UUID(signal.market_id) if isinstance(signal.market_id, str) else None
                                except (ValueError, AttributeError):
                                    market_uuid = None

                                created = await signal_service.create_signal(
                                    market_id=market_uuid,
                                    signal_type=strategy_name,
                                    direction=signal.signal,
                                    confidence=signal.confidence,
                                    reasoning=signal.reason,
                                    source_agent=strategy_name,
                                    source_data=signal.feature_values,
                                    ttl_minutes=60,
                                )

                                event_payload = {
                                    "signal_id": str(created.id),
                                    "strategy": strategy_name,
                                    "confidence": signal.confidence,
                                    "market_id": signal.market_id or data.get("condition_id"),
                                    "market_condition_id": signal.market_condition_id or data.get("condition_id"),
                                    "side": side,
                                    "outcome": outcome,
                                    "size": size,
                                }

                                from app.services.invariant_guard import validate_signal_fields, dead_letter_signals
                                errors = validate_signal_fields(event_payload)
                                if errors:
                                    dead_letter_signals.append({"data": event_payload, "errors": errors, "stage": "signal_agent_reject"})
                                    logger.warning("signal_skip_invalid_output", errors=errors, strategy=strategy_name)
                                    continue

                                await EventBus.publish(
                                    "signal:generated",
                                    "signal.generated",
                                    self.name,
                                    {
                                        **event_payload,
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
