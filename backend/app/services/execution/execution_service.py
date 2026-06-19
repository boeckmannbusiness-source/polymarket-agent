import asyncio
import time
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade, ExchangeOrder
from app.exchanges import ExchangeAdapterRegistry
from app.domain.execution import ExecutionIntent, ExecutionResult, Instrument
from app.domain.markets import InstrumentId
from app.domain.signals import Signal, SignalAction
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.services.execution.translators import GenericTranslator, PolymarketTranslator
from app.services.market_registry import MarketRegistry
from app.services.planning import Planner, create_default_planner
from app.core.logging import logger
from app.core import metrics
from app.services.control.control_plane import control_plane
from app.services.risk.circuit_breakers import cb_system, track_execution_failure, track_execution_latency
from app.services.audit.audit_logger import emit, audit_context


REDIS_QUERY_TIMEOUT = 5.0
DB_QUERY_TIMEOUT = 10.0
ADAPTER_TIMEOUT = 30.0

_execution_locks: dict[str, asyncio.Lock] = {}
_TRACE_ID: int = 0

# Execution lifecycle metrics
execution_result_total = metrics.Counter(
    "polymarket_execution_result_total", "Total execution results", ["adapter", "status"]
)
execution_result_success_total = metrics.Counter(
    "polymarket_execution_result_success_total", "Successful execution results", ["adapter"]
)
execution_result_failed_total = metrics.Counter(
    "polymarket_execution_result_failed_total", "Failed execution results", ["adapter"]
)
execution_result_latency_ms = metrics.Histogram(
    "polymarket_execution_result_latency_ms", "Execution result latency (ms)", buckets=[10, 25, 50, 100, 250, 500, 1000, 5000, 10000, 30000]
)
execution_result_shadow_total = metrics.Counter(
    "polymarket_execution_result_shadow_total", "Shadow execution results tracked"
)

# Sprint 1.4 instruction-level metrics
execution_instruction_total = metrics.Counter(
    "polymarket_execution_instruction_total", "Total instructions executed", ["adapter", "instruction_type"]
)
execution_fill_total = metrics.Counter(
    "polymarket_execution_fill_total", "Total fills generated", ["adapter"]
)
execution_slippage_bps_histogram = metrics.Histogram(
    "polymarket_execution_slippage_bps", "Slippage in bps per execution",
    buckets=[0, 5, 10, 25, 50, 100, 200, 500, 1000],
)
execution_fee_total_lamports = metrics.Counter(
    "polymarket_execution_fee_total_lamports", "Total fees in lamports", ["adapter"]
)
execution_route_complexity = metrics.Gauge(
    "polymarket_execution_route_complexity", "Route complexity (number of hops)", ["route_type"]
)

# Sprint 1.5 shadow feedback loop metrics
shadow_portfolio_updates_total = metrics.Counter(
    "polymarket_shadow_portfolio_updates_total", "Shadow portfolio updates applied"
)
shadow_position_projection_total = metrics.Counter(
    "polymarket_shadow_position_projection_total", "Shadow position projections generated"
)
shadow_execution_feedback_total = metrics.Counter(
    "polymarket_shadow_execution_feedback_total", "Shadow execution feedback records created"
)
shadow_route_efficiency_histogram = metrics.Histogram(
    "polymarket_shadow_route_efficiency", "Route efficiency score (0-1)",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# Sprint 1.7 replay & determinism metrics
replay_execution_total = metrics.Counter(
    "polymarket_replay_execution_total", "Total replay executions"
)
replay_determinism_failures_total = metrics.Counter(
    "polymarket_replay_determinism_failures_total", "Replay determinism mismatches"
)
replay_fingerprint_mismatch_total = metrics.Counter(
    "polymarket_replay_fingerprint_mismatch_total", "Replay fingerprint mismatches"
)
replay_validation_latency_ms = metrics.Histogram(
    "polymarket_replay_validation_latency_ms", "Replay validation latency (ms)",
    buckets=[1, 5, 10, 25, 50, 100, 250],
)
shadow_projected_pnl = metrics.Gauge(
    "polymarket_shadow_projected_pnl", "Projected PnL from shadow feedback", ["execution_id"]
)


def _next_trace_id() -> str:
    global _TRACE_ID
    _TRACE_ID += 1
    return f"exec_{int(time.time())}_{_TRACE_ID}"


async def _db_call(call_name: str, coro, timeout: float = DB_QUERY_TIMEOUT):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("db_query_timeout", operation=call_name, timeout=timeout)
        raise


def _get_execution_lock(market_id: str) -> asyncio.Lock:
    if market_id not in _execution_locks:
        _execution_locks[market_id] = asyncio.Lock()
    return _execution_locks[market_id]


class ExecutionSafetyError(Exception):
    pass


class ExecutionService:
    def __init__(self, db: AsyncSession, planner: Planner | None = None):
        self.db = db
        self._planner = planner or create_default_planner()

    def _get_adapter(self, engine_type: str):
        adapter_cls = ExchangeAdapterRegistry.get(engine_type)
        if adapter_cls is None:
            raise ValueError(f"Unknown engine_type: {engine_type}. No adapter registered.")
        return adapter_cls(self.db)

    async def _check_safety(self, trade: Trade | None = None, trace_id: str = ""):
        if not await control_plane.is_trading_enabled():
            await emit("EXECUTION_BLOCKED", "safety", trace_id, {"reason": "global_trading_disabled"})
            raise ExecutionSafetyError("Global trading disabled by control plane")

        if trade and trade.agent_id and await control_plane.is_strategy_paused(trade.agent_id):
            await emit("EXECUTION_BLOCKED", "safety", trace_id, {"reason": f"strategy_paused:{trade.agent_id}"})
            raise ExecutionSafetyError(f"Strategy paused: {trade.agent_id}")

        if trade and trade.market_id and await control_plane.is_market_paused(trade.market_id):
            await emit("EXECUTION_BLOCKED", "safety", trace_id, {"reason": f"market_paused:{trade.market_id}"})
            raise ExecutionSafetyError(f"Market paused: {trade.market_id}")

        active_breakers = await cb_system.get_active()
        if active_breakers:
            names = [b.get("name") for b in active_breakers]
            await emit("EXECUTION_BLOCKED", "safety", trace_id, {"reason": f"active_breakers:{names}"})
            raise ExecutionSafetyError(f"Active circuit breakers: {names}")

    async def _kill_switch_recheck(self, trade: Trade | None = None, trace_id: str = ""):
        can_trade = await control_plane.is_trading_enabled()
        await emit("KILLSWITCH_RECHECK", "safety", trace_id, {"trading_enabled": can_trade})
        if not can_trade:
            raise ExecutionSafetyError("Kill-switch engaged after lock acquisition")

        if trade and trade.market_id:
            if await control_plane.is_market_paused(trade.market_id):
                raise ExecutionSafetyError(f"Market paused after lock: {trade.market_id}")

        active_breakers = await cb_system.get_active()
        if active_breakers:
            names = [b.get("name") for b in active_breakers]
            raise ExecutionSafetyError(f"Breaker engaged after lock acquisition: {names}")

    async def resolve_instrument(self, venue: str, symbol: str,
                                 asset_identifier: str | None = None,
                                 quote_asset: str = "USDC",
                                 metadata: dict | None = None) -> Instrument:
        instr_id = InstrumentId(venue=venue, symbol=symbol, quote_asset=quote_asset)
        resolution = await MarketRegistry.resolve(instr_id)
        enriched_meta = dict(metadata or {})
        if resolution.market and resolution.market.metadata:
            enriched_meta.update(resolution.market.metadata)
        return Instrument(
            venue=venue,
            symbol=symbol,
            asset_identifier=asset_identifier or symbol,
            quote_asset=quote_asset,
            metadata=enriched_meta or None,
        )

    def _build_intent(self, trade: Trade, engine_type: str, side: str | None = None,
                      quantity: Decimal | None = None, limit_price: Decimal | None = None,
                      metadata: dict | None = None) -> ExecutionIntent:
        instrument = Instrument(
            venue=engine_type,
            symbol=str(trade.market_id) if trade.market_id else "",
            asset_identifier=trade.asset_in or str(trade.market_id) if trade.market_id else "",
            quote_asset=trade.asset_out or "USDC",
            metadata={"outcome": trade.outcome} if trade.outcome else None,
        )
        return ExecutionIntent(
            instrument=instrument,
            side=side or trade.side,
            quantity=quantity or Decimal(str(trade.size)),
            order_type=trade.order_type or "market",
            limit_price=limit_price or (Decimal(str(trade.price)) if trade.price is not None else None),
            slippage_bps=None,
            strategy_id=str(trade.agent_id) if trade.agent_id else None,
            metadata=metadata or {"trade_id": str(trade.id)},
        )

    async def _signal_to_intent(self, signal: Signal, engine_type: str = "paper") -> ExecutionIntent:
        action_to_side = {
            SignalAction.BUY: "buy",
            SignalAction.SELL: "sell",
        }
        side = action_to_side.get(signal.action, "buy")
        resolved = await self.resolve_instrument(
            venue=signal.instrument.venue,
            symbol=signal.instrument.symbol,
            asset_identifier=signal.instrument.asset_identifier,
            quote_asset=signal.instrument.quote_asset,
            metadata=signal.instrument.metadata,
        )
        slippage = int(signal.instrument.metadata.get("slippage_bps", 100)) if signal.instrument.metadata else 100
        constraints = ExecutionConstraints(max_slippage_bps=slippage)
        plan = await self._planner.plan(
            instrument=resolved,
            amount_in=signal.quantity or Decimal("0"),
            side=side,
            constraints=constraints,
        )
        return ExecutionIntent(
            instrument=resolved,
            side=side,
            quantity=signal.quantity or Decimal("0"),
            order_type="market",
            strategy_id=signal.metadata.get("strategy_id") if signal.metadata else None,
            metadata=signal.metadata,
            transaction_plan=plan,
        )

    async def execute_signal(self, signal: Signal, engine_type: str = "paper"):
        trace_id = _next_trace_id()
        intent = await self._signal_to_intent(signal, engine_type)
        await emit("signal.received", "signal", intent.instrument.symbol, {
            "trace_id": trace_id,
            "action": signal.action.value,
            "engine_type": engine_type,
        })
        result = await self.submit_intent(intent, trace_id=trace_id)
        await self._propagate_execution_result(result, trace_id=trace_id)
        return result

    async def _propagate_execution_result(self, result: ExecutionResult, trade: Trade | None = None, trace_id: str = ""):
        execution_result_total.labels(adapter=result.adapter, status=result.status).inc()
        if result.status in ("filled", "submitted", "complete"):
            execution_result_success_total.labels(adapter=result.adapter).inc()
        elif result.status in ("failed", "cancelled", "rejected"):
            execution_result_failed_total.labels(adapter=result.adapter).inc()
        if result.latency_ms is not None:
            execution_result_latency_ms.observe(result.latency_ms)

        event_type = f"execution.{result.status}"
        await emit(event_type, "execution", result.execution_id, {
            "trace_id": trace_id,
            "adapter": result.adapter,
            "status": result.status,
            "quantity": str(result.quantity_executed) if result.quantity_executed else None,
            "price": str(result.average_price) if result.average_price else None,
            "fees": str(result.fees) if result.fees else None,
            "latency_ms": result.latency_ms,
            "trade_id": str(trade.id) if trade else None,
        })

        fills_count = len(result.fills) if result.fills else 0
        logger.info(
            "execution_result_emitted",
            execution_id=result.execution_id,
            status=result.status,
            adapter=result.adapter,
            fills=fills_count,
            latency_ms=result.latency_ms,
            trace_id=trace_id,
        )

        if result.fills:
            execution_fill_total.labels(adapter=result.adapter).inc(len(result.fills))
        if result.simulated_slippage is not None:
            execution_slippage_bps_histogram.observe(result.simulated_slippage * 10000)
        if result.fees is not None:
            execution_fee_total_lamports.labels(adapter=result.adapter).inc(float(result.fees * Decimal("1000000")))
        if result.execution_path:
            execution_route_complexity.labels(route_type="DIRECT" if len(result.execution_path) <= 1 else "SPLIT").set(len(result.execution_path))
        if result.instruction_trace:
            for instr_type in result.instruction_trace:
                execution_instruction_total.labels(adapter=result.adapter, instruction_type=instr_type).inc()
                if result.execution_path:
                    execution_route_complexity.labels(route_type="DIRECT" if len(result.execution_path) <= 1 else "SPLIT").set(len(result.execution_path))

        try:
            from app.services.shadow.shadow_execution_service import shadow_execution_service
            exec_meta = result.metadata or {}
            await shadow_execution_service.create_execution(
                signal_id=exec_meta.get("trade_id", ""),
                market_id=exec_meta.get("market_id", ""),
                strategy=exec_meta.get("strategy_id", "unknown"),
                direction=exec_meta.get("side", "buy"),
                outcome=exec_meta.get("outcome", ""),
                size=float(result.quantity_executed or 0),
                entry_price=float(result.average_price or 0),
            )
            execution_result_shadow_total.inc()
        except Exception as e:
            logger.debug("shadow_execution_log_skipped", error=str(e))

        await self._shadow_feedback_loop(result, trace_id=trace_id)
        await self._replay_integration(result, trace_id=trace_id)

    async def _shadow_feedback_loop(self, result: ExecutionResult, trace_id: str = "") -> None:
        try:
            from app.services.shadow.portfolio_projector import PortfolioProjector
            from app.services.shadow.shadow_portfolio import ShadowPortfolio
            from app.services.shadow.execution_feedback_service import ExecutionFeedbackService

            projector = PortfolioProjector()
            shadow_portfolio = ShadowPortfolio()
            feedback_service = ExecutionFeedbackService(projector)

            projections = projector.project(result, current=None)
            if projections:
                shadow_position_projection_total.inc(len(projections))

            snapshot = shadow_portfolio.apply(result, current=None)
            shadow_portfolio_updates_total.inc()

            feedback = feedback_service.create(result, snapshot)
            shadow_execution_feedback_total.inc()
            shadow_route_efficiency_histogram.observe(feedback.route_efficiency)
            shadow_projected_pnl.labels(execution_id=result.execution_id).set(feedback.portfolio_delta)

            await emit("shadow.execution.completed", "shadow", result.execution_id, {
                "trace_id": trace_id,
                "execution_id": result.execution_id,
                "status": result.status,
                "projections": len(projections),
                "portfolio_delta": round(feedback.portfolio_delta, 4),
                "route_efficiency": round(feedback.route_efficiency, 4),
                "slippage_bps": round(feedback.slippage_realized, 2),
                "latency_ms": round(feedback.latency_ms, 2),
            })

            await self._consistency_validation(result, snapshot, projections, feedback, trace_id)
        except Exception as e:
            logger.debug("shadow_feedback_loop_skipped", error=str(e), trace_id=trace_id)

    async def _consistency_validation(
        self,
        result: ExecutionResult,
        snapshot: PortfolioSnapshot,
        projections: list[PositionProjection],
        feedback: ExecutionFeedback,
        trace_id: str = "",
    ) -> None:
        try:
            from app.services.consistency.execution_consistency_layer import ExecutionConsistencyLayer

            layer = ExecutionConsistencyLayer()
            bundle = layer.validate(result, snapshot, projections, feedback)

            await emit("execution.consistency.validated", "consistency", result.execution_id, {
                "trace_id": trace_id,
                "execution_id": result.execution_id,
                "all_passed": bundle.report.all_passed,
                "checks": len(bundle.report.checks),
                "failed": len(bundle.report.failed_checks),
            })

            if not bundle.report.all_passed:
                for check in bundle.report.failed_checks:
                    logger.warning(
                        "consistency_check_failed",
                        execution_id=result.execution_id,
                        check=check.name,
                        expected=check.expected,
                        actual=check.actual,
                        trace_id=trace_id,
                    )
        except Exception as e:
            logger.debug("consistency_validation_skipped", error=str(e), trace_id=trace_id)

    async def create_trade_execution(self, trade: Trade):
        trace_id = _next_trace_id()
        await self._check_safety(trade, trace_id)
        engine_type = trade.trade_type or "paper"

        intent = self._build_intent(trade, engine_type)

        await emit("trade.created", "trade", str(trade.id), {
            "trace_id": trace_id,
            "engine_type": engine_type,
            "side": trade.side,
            "size": str(trade.size),
            "price": str(trade.price) if trade.price else None,
        })

        result = await self.submit_intent(intent, trace_id=trace_id)
        await self._propagate_execution_result(result, trade, trace_id)
        return result

    async def submit_intent(self, intent: ExecutionIntent, trace_id: str | None = None):
        trace_id = trace_id or _next_trace_id()
        engine_type = intent.instrument.venue

        await self._check_safety(trace_id=trace_id)

        market_id = intent.instrument.symbol or "unknown"
        lock = _get_execution_lock(market_id)
        async with lock:
            await self._kill_switch_recheck(trace_id=trace_id)
            adapter = self._get_adapter(engine_type)
            start = time.time()
            try:
                result = await asyncio.wait_for(adapter.submit_order(intent), timeout=ADAPTER_TIMEOUT)
            except asyncio.TimeoutError:
                elapsed_ms = (time.time() - start) * 1000
                track_execution_failure()
                track_execution_latency(elapsed_ms)
                await emit("TIMEOUT_HIT", "safety", trace_id, {
                    "engine": engine_type,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "timeout": ADAPTER_TIMEOUT,
                    "market_id": market_id,
                })
                logger.error(
                    "adapter_submit_order_timeout",
                    engine=engine_type,
                    trace_id=trace_id,
                    elapsed_ms=round(elapsed_ms, 2),
                )
                result = ExecutionResult(
                    execution_id=str(uuid.uuid4()),
                    adapter=engine_type,
                    status="failed",
                    metadata={"error": "adapter_timeout", "trace_id": trace_id},
                )
                execution_result_total.labels(adapter=engine_type, status="failed").inc()
                execution_result_failed_total.labels(adapter=engine_type).inc()
                return result

            elapsed_ms = (time.time() - start) * 1000
            track_execution_latency(elapsed_ms)

            with audit_context(order_id=result.execution_id):
                await emit("order.submitted", "execution", result.execution_id, {
                    "trace_id": trace_id,
                    "adapter": result.adapter,
                    "status": result.status,
                    "latency_ms": round(elapsed_ms, 2),
                })

            return result

    async def close_trade_execution(self, trade: Trade, exit_price: Decimal | None = None):
        trace_id = _next_trace_id()
        await self._check_safety(trade, trace_id)

        result = await _db_call(
            "select_filled_order",
            self.db.execute(
                select(ExchangeOrder)
                .where(
                    ExchangeOrder.trade_id == trade.id,
                    ExchangeOrder.status.in_(["filled", "partially_filled"]),
                )
                .order_by(ExchangeOrder.order_num)
                .limit(1)
            ),
        )
        original_order = result.scalar_one_or_none()
        if not original_order:
            raise ValueError(f"No filled ExchangeOrder found for trade {trade.id}")

        if exit_price is not None:
            resolved_price = Decimal(str(exit_price))
        else:
            resolved_price = original_order.filled_price or Decimal("0.5")

        close_side = "sell" if original_order.side == "buy" else "buy"

        intent = self._build_intent(
            trade,
            engine_type=original_order.engine_type,
            side=close_side,
            quantity=original_order.filled_size,
            limit_price=resolved_price,
            metadata={"closing_order": True, "original_order_id": str(original_order.id), "trade_id": str(trade.id)},
        )

        result = await self.submit_intent(intent, trace_id=trace_id)
        await self._propagate_execution_result(result, trade, trace_id)
        return result
