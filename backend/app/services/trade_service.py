import uuid
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Trade, Market
from app.schemas.trade import TradeCreateRequest
from app.services.risk_service import RiskService
from app.engines.paper_engine import PaperEngine
from app.core.exceptions import TradeExecutionError, MarketNotFoundError


class TradeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.risk_service = RiskService(db)
        self.paper_engine = PaperEngine(db)
        self._emergency_stop = False

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
        if self._emergency_stop:
            raise TradeExecutionError("Emergency stop is active. No trades allowed.")

        market = await self.db.execute(select(Market).where(Market.id == request.market_id))
        if not market.scalar_one_or_none():
            raise MarketNotFoundError(f"Market {request.market_id} not found")

        risk_check = await self.risk_service.validate_trade(
            market_id=request.market_id,
            side=request.side,
            size=request.size,
            confidence=1.0,
            agent_id=request.agent_id,
        )

        if not risk_check.approved:
            raise TradeExecutionError(f"Risk check failed: {risk_check.reason}")

        trade = Trade(
            id=uuid.uuid4(),
            market_id=request.market_id,
            signal_id=request.signal_id,
            trade_type=settings.TRADING_MODE,
            status="pending",
            side=request.side,
            outcome=request.outcome,
            order_type=request.order_type,
            size=request.size,
            price=request.price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            reason=request.reason,
            agent_id=request.agent_id,
        )
        self.db.add(trade)
        await self.db.flush()

        if request.order_type == "market":
            result = await self.paper_engine.execute_market_order(trade)
            trade.status = result["status"]
            trade.filled_size = result["filled_size"]
            trade.filled_price = result["filled_price"]
            trade.slippage = result["slippage"]
            trade.fee = result["fee"]
            trade.entry_timestamp = datetime.now(timezone.utc)

        await self.db.flush()
        return trade

    async def close_trade(self, trade_id: uuid.UUID) -> Trade:
        trade = await self.get_trade(trade_id)
        if trade.status not in ("open", "pending"):
            raise TradeExecutionError(f"Trade {trade_id} is {trade.status}, cannot close")

        result = await self.paper_engine.close_position(trade)
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
