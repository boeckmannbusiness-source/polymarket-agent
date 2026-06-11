import asyncio
import uuid

from app.agents.base import BaseAgent
from app.core.events import EventBus
from app.core.logging import logger
from app.core.timing import record_latency
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
                    correlation_id = msg.get("correlation_id")

                    enrichment = {}
                    async with async_session_factory() as db:
                        enrichment = await MarketEnrichmentService(db).enrich(
                            data.get("condition_id") or data.get("market_condition_id")
                        )
                    data.update(enrichment)

                    strategy_names = get_strategy_names()
                    ensemble_enabled = "ensemble" in strategy_names
                    if ensemble_enabled:
                        from app.strategies import get_strategy as _gs
                        ens = _gs("ensemble")
                        if not ens.config.enabled:
                            ensemble_enabled = False

                    if ensemble_enabled:
                        for name in strategy_names:
                            if name == "ensemble":
                                await self._process_strategy(data, name, msg, correlation_id)
                    else:
                        for name in strategy_names:
                            await self._process_strategy(data, name, msg, correlation_id)

                    await EventBus.ack_message(r, "wallet:trade", "signal_agent", msg["id"])

            except Exception as e:
                logger.error("signal_agent_error", error=str(e))

            await asyncio.sleep(0.5)

    async def _process_strategy(self, data: dict, strategy_name: str, msg: dict, correlation_id: str | None = None):
        _start = __import__("time").perf_counter_ns()
        async with async_session_factory() as db:
            try:
                strategy_service = StrategyService(db)
                signal_service = SignalService(db)

                config_row = await strategy_service.get_config(strategy_name)
                config = config_row.config if config_row else None

                strategy = get_strategy(strategy_name, config=config)
                if not strategy.config.enabled:
                    return

                signal = await strategy.generate_signal(data)
                if signal is None:
                    return

                side = data.get("side", "buy")
                outcome = data.get("outcome", "YES")
                whale_trade_size = float(data.get("value", data.get("size", 0)) or 0)

                max_position_size = 10.0
                recommended_position_size = round(max_position_size * signal.confidence, 2)
                recommended_position_size = max(0.01, min(max_position_size, recommended_position_size))

                logger.info(
                    "position_size_computed",
                    whale_trade_size=whale_trade_size,
                    confidence=signal.confidence,
                    recommended_position_size=recommended_position_size,
                )

                try:
                    market_uuid = uuid.UUID(signal.market_id) if isinstance(signal.market_id, str) else None
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
                    correlation_id=correlation_id,
                )

                event_payload = {
                    "signal_id": str(created.id),
                    "strategy": strategy_name,
                    "confidence": signal.confidence,
                    "market_id": signal.market_id or data.get("condition_id"),
                    "market_condition_id": signal.market_condition_id or data.get("condition_id"),
                    "side": side,
                    "outcome": outcome,
                    "whale_trade_size": whale_trade_size,
                    "recommended_position_size": recommended_position_size,
                    "size": recommended_position_size,
                }

                from app.services.invariant_guard import validate_signal_fields, dead_letter_signals
                errors = validate_signal_fields(event_payload)
                if errors:
                    dead_letter_signals.append({"data": event_payload, "errors": errors, "stage": "signal_agent_reject"})
                    logger.warning("signal_skip_invalid_output", errors=errors, strategy=strategy_name)
                    return

                record_latency("signal_generation", (__import__("time").perf_counter_ns() - _start) / 1_000_000, labels={"strategy": strategy_name})

                await EventBus.publish(
                    "signal:generated",
                    "signal.generated",
                    self.name,
                    {
                        **event_payload,
                        "reasoning": signal.reason[:200],
                        "risk_score": signal.risk_score,
                    },
                    correlation_id=correlation_id,
                )
                await self.log_event("signal_generated", {
                    "strategy": strategy_name,
                    "signal_id": str(created.id),
                    "signal": signal.signal,
                    "confidence": signal.confidence,
                    "whale_trade_size": whale_trade_size,
                    "recommended_position_size": recommended_position_size,
                }, correlation_id=correlation_id)

                await db.commit()

            except Exception as e:
                await db.rollback()
                logger.error(
                    "strategy_isolation_error",
                    strategy=strategy_name,
                    error=str(e),
                )
