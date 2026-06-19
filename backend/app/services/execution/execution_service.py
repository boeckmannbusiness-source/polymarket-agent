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
from app.services.execution.translators import GenericTranslator, PolymarketTranslator
from app.services.market_registry import MarketRegistry
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
    def __init__(self, db: AsyncSession):
        self.db = db

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
        return ExecutionIntent(
            instrument=resolved,
            side=side,
            quantity=signal.quantity or Decimal("0"),
            order_type="market",
            strategy_id=signal.metadata.get("strategy_id") if signal.metadata else None,
            metadata=signal.metadata,
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
