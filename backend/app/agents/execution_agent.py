import asyncio
from uuid import UUID

from sqlalchemy import select

from app.agents.base import BaseAgent
from app.core.events import EventBus
from app.core.logging import logger
from app.core.timing import record_latency
from app.database import async_session_factory
from app.models import Trade
from app.services.trade_service import TradeService, FORCE_TRADING_DISABLED, MICRO_LIVE_SAFE_MODE
from app.schemas.trade import TradeCreateRequest
from app.services.invariant_guard import validate_signal_fields, dead_letter_signals
from app.services.global_risk_guard import GlobalRiskGuard
from app.services.pipeline_metrics import inc_execution_failure, inc_trading_halt


class ExecutionAgent(BaseAgent):
    name = "execution_agent"

    async def setup(self):
        logger.info("execution_agent_setup")

    async def loop(self):
        while self.running:
            try:
                if FORCE_TRADING_DISABLED:
                    logger.warning("exec_kill_switch_active_no_trades")
                    await asyncio.sleep(5)
                    continue

                r = await EventBus.subscribe_to_stream("trade:request", "execution_agent", "exec_1")
                messages = await EventBus.read_stream(r, "trade:request", "execution_agent", "exec_1", block=5000)

                for msg in messages:
                    data = msg.get("data", {})
                    event_type = msg.get("event_type", "")
                    correlation_id = msg.get("correlation_id")

                    if event_type == "trade.risk_approved":
                        errors = validate_signal_fields(data)
                        if errors:
                            dead_letter_signals.append({"data": data, "errors": errors, "stage": "execution_agent_reject"})
                            logger.warning("exec_skip_invalid_signal", errors=errors, signal_id=data.get("signal_id"))
                        else:
                            await self.execute_trade(data, correlation_id)

                    await EventBus.ack_message(r, "trade:request", "execution_agent", msg["id"])

            except Exception as e:
                logger.error("execution_agent_error", error=str(e))

            await asyncio.sleep(0.5)

    async def _check_risk_overlay(self) -> bool:
        from app.services.risk_overlay import RiskOverlay
        async with async_session_factory() as db:
            overlay = RiskOverlay(db)
            state = await overlay.check()
            self._last_risk_state = state
            if state.status == "MARKET_DATA_UNSTABLE":
                await inc_trading_halt("MARKET_DATA_UNSTABLE")
                logger.warning("exec_trading_halt_market_data_unstable")
                return False
            if state.status == "STOPPED":
                logger.warning("exec_trading_halt", reason=state.reason)
                return False
            return True

    async def _check_micro_live(self, data: dict) -> bool:
        if not MICRO_LIVE_SAFE_MODE:
            return True
        strategy = data.get("strategy", "")
        if strategy != "crisis_reversion":
            logger.warning("exec_micro_live_reject_strategy", strategy=strategy)
            return False
        price = data.get("price", 1.0)
        if price is not None and float(price) >= 0.20:
            logger.warning("exec_micro_live_reject_price", price=price)
            return False
        from app.services.pipeline_metrics import get_metrics
        metrics = await get_metrics()
        if metrics.get("live_daily_pnl", 0.0) <= -2.0:
            logger.warning("exec_micro_live_daily_loss_limit")
            return False
        return True

    async def execute_trade(self, data: dict, correlation_id: str | None = None):
        from app.core.system_mode import get_mode_manager
        if not get_mode_manager().can_execute_trades():
            signal_id = data["signal_id"]
            logger.warning("exec_blocked_system_mode", signal_id=signal_id)
            await inc_execution_failure()
            await EventBus.publish(
                "trade:execution",
                "trade.failed",
                self.name,
                {"signal_id": signal_id, "error": "trading_halted_system_mode"},
                correlation_id=correlation_id,
            )
            await self.log_event("trade_failed", {"signal_id": signal_id, "error": "trading_halted_system_mode"}, correlation_id=correlation_id)
            return

        _start = __import__("time").perf_counter_ns()
        signal_id = data["signal_id"]
        market_id = data["market_id"]
        condition_id = data.get("condition_id")
        side = data["side"]
        outcome = data["outcome"]
        size = data["size"]
        confidence = data.get("confidence", 0.0)
        strategy = data.get("strategy", "unknown")

        if not outcome or not isinstance(outcome, str):
            logger.warning("exec_skip_invalid_outcome", signal_id=signal_id, outcome=outcome)
            return
        if side not in ("buy", "sell"):
            logger.warning("exec_skip_invalid_side", signal_id=signal_id, side=side)
            return
        if not isinstance(size, (int, float)) or size <= 0:
            logger.warning("exec_skip_invalid_size", signal_id=signal_id, size=size)
            return

        try:
            market_uuid = UUID(market_id) if isinstance(market_id, str) else market_id
        except (ValueError, AttributeError):
            logger.warning("exec_skip_invalid_market_id", signal_id=signal_id)
            return

        trading_allowed = await self._check_risk_overlay()
        if not trading_allowed:
            await inc_execution_failure()
            await EventBus.publish(
                "trade:execution",
                "trade.failed",
                self.name,
                {"signal_id": signal_id, "market_id": market_id, "strategy": strategy, "error": "trading_halted_risk_overlay"},
                correlation_id=correlation_id,
            )
            await self.log_event("trade_failed", {"signal_id": signal_id, "error": "trading_halted"}, correlation_id=correlation_id)
            return

        micro_live_ok = await self._check_micro_live(data)
        if not micro_live_ok:
            await inc_execution_failure()
            await EventBus.publish(
                "trade:execution",
                "trade.failed",
                self.name,
                {"signal_id": signal_id, "market_id": market_id, "strategy": strategy, "error": "micro_live_restrictions"},
                correlation_id=correlation_id,
            )
            await self.log_event("trade_failed", {"signal_id": signal_id, "error": "micro_live_restrictions"}, correlation_id=correlation_id)
            return

        async with async_session_factory() as db:
            guard = GlobalRiskGuard(db)
            exposure_check = await guard.check_exposure(
                market_id=str(market_uuid),
                outcome=outcome,
                proposed_size=float(size),
                proposed_price=float(data.get("price", 0)),
            )
            if not exposure_check.approved:
                await inc_execution_failure()
                await EventBus.publish(
                    "trade:execution",
                    "trade.failed",
                    self.name,
                    {"signal_id": signal_id, "market_id": market_id, "strategy": strategy, "error": f"exposure_limit:{exposure_check.reason}"},
                    correlation_id=correlation_id,
                )
                await self.log_event("trade_failed", {"signal_id": signal_id, "error": exposure_check.reason}, correlation_id=correlation_id)
                return

            existing = await db.execute(
                select(Trade).where(
                    Trade.market_id == market_uuid,
                    Trade.outcome == outcome,
                    Trade.status.in_(["open", "pending"]),
                )
            )
            if existing.scalar_one_or_none():
                from app.services.pipeline_metrics import inc_duplicate_market_rejection
                await inc_duplicate_market_rejection()
                await inc_execution_failure()
                await EventBus.publish(
                    "trade:execution",
                    "trade.failed",
                    self.name,
                    {"signal_id": signal_id, "market_id": market_id, "strategy": strategy, "error": "duplicate_market_position"},
                    correlation_id=correlation_id,
                )
                await self.log_event("trade_failed", {"signal_id": signal_id, "error": "duplicate_market_position"}, correlation_id=correlation_id)
                return

            service = TradeService(db)
            request = TradeCreateRequest(
                market_id=market_uuid,
                signal_id=UUID(signal_id) if signal_id else None,
                side=side,
                outcome=outcome,
                size=float(size),
                confidence=float(confidence) if confidence else 1.0,
                reason=f"Auto-execution signal={signal_id} strategy={strategy} confidence={confidence}",
                agent_id=strategy,
                correlation_id=correlation_id,
            )

            try:
                trade = await service.create_trade(request)
                from app.services.pipeline_metrics import inc_execution_success, record_slippage
                await inc_execution_success()
                if trade.slippage:
                    await record_slippage(float(trade.slippage))
                await EventBus.publish(
                    "trade:execution",
                    "trade.executed",
                    self.name,
                    {
                        "trade_id": str(trade.id),
                        "signal_id": signal_id,
                        "market_id": str(market_uuid),
                        "condition_id": condition_id,
                        "strategy": strategy,
                        "status": trade.status,
                        "side": side,
                        "outcome": outcome,
                        "size": trade.size,
                        "filled_size": float(trade.filled_size or 0),
                        "filled_price": float(trade.filled_price or 0),
                        "price": float(trade.filled_price or 0),
                        "slippage": float(trade.slippage or 0),
                        "fee": float(trade.fee or 0),
                    },
                    correlation_id=correlation_id,
                )
                await self.log_event("trade_executed", {"trade_id": str(trade.id), "signal_id": signal_id, "strategy": strategy}, correlation_id=correlation_id)
            except Exception as e:
                await inc_execution_failure()
                await EventBus.publish(
                    "trade:execution",
                    "trade.failed",
                    self.name,
                    {"signal_id": signal_id, "market_id": str(market_uuid), "strategy": strategy, "error": str(e)},
                    correlation_id=correlation_id,
                )
                await self.log_event("trade_failed", {"signal_id": signal_id, "error": str(e)}, correlation_id=correlation_id)
            finally:
                record_latency("execution", (__import__("time").perf_counter_ns() - _start) / 1_000_000)
