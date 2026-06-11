import asyncio

from app.agents.base import BaseAgent
from app.core.events import EventBus
from app.core.logging import logger
from app.core.timing import record_latency
from app.database import async_session_factory
from app.services.invariant_guard import validate_signal_fields, dead_letter_signals
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
                    data = msg.get("data", {})
                    errors = validate_signal_fields(data)
                    if errors:
                        dead_letter_signals.append({"data": data, "errors": errors, "stage": "risk_agent_reject"})
                        logger.warning("risk_skip_invalid_signal", errors=errors, signal_id=data.get("signal_id"))
                        await EventBus.ack_message(r, "signal:generated", "risk_agent", msg["id"])
                        continue

                    await self.evaluate_signal(msg)
                    await EventBus.ack_message(r, "signal:generated", "risk_agent", msg["id"])

            except Exception as e:
                logger.error("risk_agent_error", error=str(e))

            await asyncio.sleep(0.5)

    async def evaluate_signal(self, msg: dict):
        _start = __import__("time").perf_counter_ns()
        data = msg.get("data", {})
        correlation_id = msg.get("correlation_id")
        if not isinstance(data, dict):
            logger.warning("risk_skip_invalid_data_type", type=type(data).__name__)
            return
        signal_id = data.get("signal_id")
        if not signal_id:
            logger.warning("risk_skip_missing_signal_id")
            return
        market_id = data.get("market_id") or data.get("market_condition_id")
        confidence = data.get("confidence", 0.0)
        if confidence is None:
            confidence = 0.0
        side = data.get("side", "buy")
        outcome = data.get("outcome")
        size = data.get("recommended_position_size", data.get("size"))
        if size is None:
            size = 0.0
        size = float(size)

        async with async_session_factory() as db:
            risk_service = RiskService(db)
            check = await risk_service.validate_trade(
                market_id=market_id,
                side=side,
                size=size,
                confidence=confidence,
                agent_id=self.name,
            )

            if check.approved:
                from app.services.pipeline_metrics import inc_signal
                await inc_signal()
                await EventBus.publish(
                    "trade:request",
                    "trade.risk_approved",
                    self.name,
                    {
                        "signal_id": signal_id,
                        "market_id": market_id,
                        "condition_id": data.get("market_condition_id"),
                        "side": side,
                        "outcome": outcome,
                        "size": size,
                        "confidence": confidence,
                        "strategy": data.get("strategy", "unknown"),
                        "risk_check": str(check),
                    },
                    correlation_id=correlation_id,
                )
                await self.log_event("risk_approved", {"signal_id": signal_id, "confidence": confidence}, correlation_id=correlation_id)
            else:
                from app.services.pipeline_metrics import inc_risk_rejected
                await inc_risk_rejected()
                await EventBus.publish(
                    "trade:request",
                    "trade.risk_rejected",
                    self.name,
                    {"signal_id": signal_id, "reason": check.reason},
                    correlation_id=correlation_id,
                )
                await self.log_event("risk_rejected", {"signal_id": signal_id, "reason": check.reason}, correlation_id=correlation_id)

            record_latency("risk_evaluation", (__import__("time").perf_counter_ns() - _start) / 1_000_000)
