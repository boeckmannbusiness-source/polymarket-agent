import uuid
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Trade, Market
from app.schemas.trade import TradeCreateRequest
from app.core.logging import logger
from app.core.timing import record_latency
from app.services.risk_service import RiskService
from app.engines.paper_engine import PaperEngine
from app.services.integrity_service import IntegrityService
from app.services.safety_service import SafetyService
from app.core.exceptions import TradeExecutionError, MarketNotFoundError


FORCE_TRADING_DISABLED = bool(settings.FORCE_TRADING_DISABLED)
MICRO_LIVE_SAFE_MODE = bool(settings.MICRO_LIVE_SAFE_MODE)


class TradeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.risk_service = RiskService(db)
        self.paper_engine = PaperEngine(db)
        self.safety_service = SafetyService(db)
        self._emergency_stop = False
        self.integrity = IntegrityService(db)

    async def list_trades(
        self,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        trade_type: str | None = None,
    ) -> list[Trade]:
        query = select(Trade)
        if status:
            query = query.where(Trade.status == status)
        if trade_type:
            query = query.where(Trade.trade_type == trade_type)
        query = query.order_by(desc(Trade.created_at)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_trade(self, trade_id: uuid.UUID) -> Trade:
        result = await self.db.execute(select(Trade).where(Trade.id == trade_id))
        trade = result.scalar_one_or_none()
        if not trade:
            raise TradeExecutionError(f"Trade {trade_id} not found")
        return trade

    async def create_trade(self, request: TradeCreateRequest) -> Trade:
        _e2e_start = __import__("time").perf_counter_ns()
        if self._emergency_stop:
            raise TradeExecutionError("Emergency stop is active. No trades allowed.")

        if FORCE_TRADING_DISABLED:
            raise TradeExecutionError("Trading disabled by operator kill switch.")

        # Strict Confidence Resolution: None is treated as 0.0 for maximum safety (fail-closed)
        resolved_confidence = float(request.confidence) if request.confidence is not None else 0.0

        # Unified Safety Check (Circuit Breakers, Kill Switch, Stale Data, Quarantined Strategies)
        safety_check = await self.safety_service.check_trade_approval(
            strategy_name=request.agent_id or "unknown",
            size=request.size,
            confidence=resolved_confidence,
        )
        if not safety_check.approved:
            raise TradeExecutionError(f"Safety check failed: {', '.join(safety_check.reasons)}")

        market = await self.db.execute(select(Market).where(Market.id == request.market_id))
        if not market.scalar_one_or_none():
            raise MarketNotFoundError(f"Market {request.market_id} not found")

        from sqlalchemy.exc import IntegrityError
        existing = await self.db.execute(
            select(Trade).where(
                Trade.market_id == request.market_id,
                Trade.outcome == request.outcome,
                Trade.status.in_(["open", "pending"]),
            )
        )
        if existing.scalar_one_or_none():
            from app.services.pipeline_metrics import inc_duplicate_market_rejection
            await inc_duplicate_market_rejection()
            raise TradeExecutionError(
                f"Duplicate position rejected: market {request.market_id} already has open position on {request.outcome}"
            )

        if MICRO_LIVE_SAFE_MODE:
            violation = await self._check_micro_live_restrictions(request)
            if violation:
                raise TradeExecutionError(f"Micro-live safety mode: {violation}")

        # Risk and Exposure Validation
        risk_check = await self.risk_service.validate_trade(
            market_id=request.market_id,
            side=request.side,
            size=request.size,
            confidence=resolved_confidence,
            agent_id=request.agent_id,
        )
        if not risk_check.approved:
            from app.services.pipeline_metrics import inc_risk_rejected
            await inc_risk_rejected()
            raise TradeExecutionError(f"Risk check failed: {risk_check.reason}")

        from app.services.global_risk_guard import GlobalRiskGuard
        guard = GlobalRiskGuard(self.db)
        exposure_check = await guard.check_exposure(
            market_id=str(request.market_id),
            outcome=request.outcome,
            proposed_size=float(request.size),
            proposed_price=float(request.price or 0),
        )
        if not exposure_check.approved:
            from app.services.pipeline_metrics import inc_exposure_rejection
            await inc_exposure_rejection()
            raise TradeExecutionError(f"Exposure limit: {exposure_check.reason}")

        from app.services.pipeline_metrics import inc_signal
        await inc_signal()

        from app.services.portfolio_allocator import PortfolioAllocator
        allocator = PortfolioAllocator(self.db)
        allocation = await allocator.allocate(
            signal_confidence=resolved_confidence,
            strategy_name=request.agent_id or "unknown",
            market_archetype="medium_liquidity",
            regime="normal",
            current_drawdown=0.0,
        )
        adjusted_size = min(request.size, allocation.size)

        if MICRO_LIVE_SAFE_MODE and adjusted_size > 1:
            adjusted_size = 1.0

        cid = uuid.UUID(request.correlation_id) if request.correlation_id and isinstance(request.correlation_id, str) else request.correlation_id
        trade = Trade(
            id=uuid.uuid4(),
            market_id=request.market_id,
            signal_id=request.signal_id,
            correlation_id=cid,
            trade_type=settings.TRADING_MODE,
            status="pending",
            side=request.side,
            outcome=request.outcome,
            order_type=request.order_type,
            size=adjusted_size,
            price=request.price,
            reason=request.reason,
            agent_id=request.agent_id,
        )
        self.db.add(trade)
        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            from app.services.pipeline_metrics import inc_duplicate_market_rejection
            await inc_duplicate_market_rejection()
            logger.warning(
                "trade_duplicate_integrity_error",
                market_id=str(request.market_id),
                outcome=request.outcome,
                error=str(e),
            )
            raise TradeExecutionError(
                f"Duplicate position rejected (DB constraint): market {request.market_id} on {request.outcome}"
            )

        if request.order_type == "market":
            result = await self.paper_engine.execute_market_order(trade)
            trade.status = result["status"]
            trade.filled_size = result["filled_size"]
            trade.filled_price = result["filled_price"]
            trade.slippage = result["slippage"]
            trade.fee = result["fee"]
            trade.entry_timestamp = datetime.now(timezone.utc)

        await self.db.flush()

        _, integrity_failures = await self.integrity.verify_and_trace(trade, correlation_id=request.correlation_id)
        if integrity_failures:
            logger.warning("integrity_failures_on_create",
                        trade_id=str(trade.id),
                        count=len(integrity_failures),
                        failures=integrity_failures)

        e2e_ms = (__import__("time").perf_counter_ns() - _e2e_start) / 1_000_000
        record_latency("end_to_end", e2e_ms)
        return trade

    async def _check_micro_live_restrictions(self, request: TradeCreateRequest) -> str | None:
        restricted_archetypes = {"generic", "politics", "sports"}
        if request.agent_id and request.agent_id not in ("crisis_reversion",):
            return f"only crisis_reversion allowed in micro-live mode, got {request.agent_id}"
        if request.price is not None and float(request.price) >= 0.20:
            return f"price {request.price} exceeds micro-live max of 0.20"

        from app.services.pipeline_metrics import get_metrics
        metrics = await get_metrics()
        daily_pnl = metrics.get("live_daily_pnl", 0.0)
        if daily_pnl <= -2.0:
            return f"daily loss limit of $2 reached ({daily_pnl:.2f})"
        open_trades = metrics.get("live_consecutive_losses", 0)
        if open_trades >= 2:
            return f"max concurrent positions (2) would be exceeded"

        return None

    async def close_trade(self, trade_id: uuid.UUID, exit_price: float | None = None) -> Trade:
        trade = await self.get_trade(trade_id)
        if trade.status not in ("open", "pending"):
            raise TradeExecutionError(f"Trade {trade_id} is {trade.status}, cannot close")

        result = await self.paper_engine.close_position(trade, exit_price=exit_price)
        trade.status = result["status"]
        trade.pnl = result["pnl"]
        trade.pnl_percent = result["pnl_percent"]
        trade.exit_timestamp = datetime.now(timezone.utc)
        await self.db.flush()
        return trade

    async def emergency_stop(self):
        self._emergency_stop = True
        open_trades = await self.db.execute(
            select(Trade).where(Trade.status.in_(["pending", "open"]))
        )
        for trade in open_trades.scalars().all():
            trade.status = "cancelled"
        await self.db.flush()

    async def resume(self):
        self._emergency_stop = False
