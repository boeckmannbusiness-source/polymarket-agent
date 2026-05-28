import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Trade, Market, MarketEvent, Position
from app.models.portfolio import PortfolioSnapshot
from app.core.logging import logger


REGIME_SL_TP = {
    "crisis": {"stop_loss": -0.05, "take_profit": +0.12},
    "normal": {"stop_loss": -0.10, "take_profit": +0.25},
    "extreme": {"stop_loss": -0.15, "take_profit": +0.20},
    "high_volatility": {"stop_loss": -0.20, "take_profit": +0.30},
}


@dataclass
class ExitDecision:
    action: str  # "HOLD" | "EXIT"
    reason: str
    confidence: float
    exit_price: float | None = None


class ExitEngine:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._exit_tracker: dict[str, list[dict]] = {}
        self._exits_by_reason: dict[str, int] = {}
        self._forced_exit_count = 0

    async def evaluate(
        self,
        trade: Trade,
        market_state: dict[str, Any] | None = None,
        portfolio_state: dict[str, Any] | None = None,
    ) -> ExitDecision:
        if trade.status not in ("open", "pending"):
            return ExitDecision(action="HOLD", reason="trade_not_open", confidence=1.0)

        fill_price = trade.filled_price or trade.price or 0.5
        latest_price = await self._get_outcome_price(trade)
        if latest_price is None:
            latest_price = fill_price

        regime = self._detect_regime(trade, market_state)
        sl_tp = REGIME_SL_TP.get(regime, REGIME_SL_TP["normal"])
        trade_return = (latest_price - fill_price) / fill_price if fill_price > 0 else 0
        if trade.side == "sell":
            trade_return = -trade_return

        sl_hit = trade_return <= sl_tp["stop_loss"]
        tp_hit = trade_return >= sl_tp["take_profit"]

        if sl_hit:
            self._forced_exit_count += 1
            self._exits_by_reason["stop_loss"] = self._exits_by_reason.get("stop_loss", 0) + 1
            return ExitDecision(
                action="EXIT",
                reason=f"stop_loss_hit: regime={regime} return={trade_return:.4f} sl={sl_tp['stop_loss']:.4f}",
                confidence=0.95,
                exit_price=latest_price,
            )

        if tp_hit:
            self._forced_exit_count += 1
            self._exits_by_reason["take_profit"] = self._exits_by_reason.get("take_profit", 0) + 1
            return ExitDecision(
                action="EXIT",
                reason=f"take_profit_hit: regime={regime} return={trade_return:.4f} tp={sl_tp['take_profit']:.4f}",
                confidence=0.90,
                exit_price=latest_price,
            )

        max_hold = await self._check_max_holding_time(trade)
        if max_hold:
            self._forced_exit_count += 1
            self._exits_by_reason["max_holding_time"] = self._exits_by_reason.get("max_holding_time", 0) + 1
            return ExitDecision(
                action="EXIT",
                reason="max_holding_time_exceeded",
                confidence=0.80,
                exit_price=latest_price,
            )

        regime_flip = await self._detect_regime_flip(trade, regime)
        if regime_flip:
            self._forced_exit_count += 1
            self._exits_by_reason["regime_flip"] = self._exits_by_reason.get("regime_flip", 0) + 1
            return ExitDecision(
                action="EXIT",
                reason=f"regime_flip_detected: {regime_flip}",
                confidence=0.75,
                exit_price=latest_price,
            )

        liquidity_col = await self._detect_liquidity_collapse(trade)
        if liquidity_col:
            self._forced_exit_count += 1
            self._exits_by_reason["liquidity_collapse"] = self._exits_by_reason.get("liquidity_collapse", 0) + 1
            return ExitDecision(
                action="EXIT",
                reason="liquidity_collapse_detected",
                confidence=0.85,
                exit_price=latest_price,
            )

        corr_spike = await self._detect_correlation_risk(trade)
        if corr_spike:
            self._forced_exit_count += 1
            self._exits_by_reason["correlation_risk"] = self._exits_by_reason.get("correlation_risk", 0) + 1
            return ExitDecision(
                action="EXIT",
                reason=f"correlation_risk_spike: {corr_spike}",
                confidence=0.70,
                exit_price=latest_price,
            )

        return ExitDecision(action="HOLD", reason="no_exit_triggered", confidence=0.95)

    async def evaluate_all_open(self) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(Trade).where(Trade.status.in_(["open", "pending"]))
        )
        trades = list(result.scalars().all())
        decisions = []
        for trade in trades:
            decision = await self.evaluate(trade)
            decisions.append({
                "trade_id": str(trade.id),
                "action": decision.action,
                "reason": decision.reason,
                "confidence": decision.confidence,
                "exit_price": decision.exit_price,
            })
        return decisions

    async def _get_outcome_price(self, trade: Trade) -> float | None:
        if not trade.market_id:
            return None
        result = await self.db.execute(
            select(MarketEvent)
            .where(MarketEvent.market_id == trade.market_id)
            .where(MarketEvent.event_type.in_(["price_change", "trade"]))
            .where(MarketEvent.price.isnot(None))
            .order_by(MarketEvent.timestamp.desc())
            .limit(1)
        )
        event = result.scalar_one_or_none()
        if event is None or event.price is None:
            return None
        price = float(event.price)
        if trade.outcome == "NO":
            return 1.0 - price
        return price

    def _detect_regime(self, trade: Trade, market_state: dict | None) -> str:
        if market_state and "regime" in market_state:
            r = market_state["regime"]
            if r in REGIME_SL_TP:
                return r
        return "normal"

    async def _check_max_holding_time(self, trade: Trade) -> bool:
        if not trade.entry_timestamp:
            return False
        elapsed = datetime.now(timezone.utc) - trade.entry_timestamp
        max_hold_hours = 168
        return elapsed > timedelta(hours=max_hold_hours)

    async def _detect_regime_flip(self, trade: Trade, current_regime: str) -> str | None:
        if not trade.entry_timestamp or not trade.market_id:
            return None
        cutoff = trade.entry_timestamp - timedelta(hours=1)
        entries = await self.db.execute(
            select(MarketEvent.price)
            .where(MarketEvent.market_id == trade.market_id)
            .where(MarketEvent.timestamp >= cutoff)
            .where(MarketEvent.timestamp <= trade.entry_timestamp)
            .where(MarketEvent.price.isnot(None))
            .order_by(MarketEvent.timestamp.asc())
        )
        prev_prices = [float(r[0]) for r in entries.all() if r[0] is not None]
        if len(prev_prices) < 3:
            return None
        start_price = prev_prices[0]
        end_price = prev_prices[-1]
        entry_return = (end_price - start_price) / start_price if start_price > 0 else 0
        abs_ret = abs(entry_return)
        if current_regime in ("normal", "low_volatility") and abs_ret > 0.15:
            return "normal_to_high_volatility"
        if current_regime in ("high_volatility", "extreme") and abs_ret < 0.02:
            return "high_volatility_to_normal"
        return None

    async def _detect_liquidity_collapse(self, trade: Trade) -> bool:
        if not trade.market_id:
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        recent = await self.db.execute(
            select(func.count(), func.coalesce(func.avg(MarketEvent.size), 0))
            .where(MarketEvent.market_id == trade.market_id)
            .where(MarketEvent.timestamp >= cutoff)
        )
        row = recent.one()
        event_count = row[0]
        avg_size = float(row[1]) if row[1] else 0
        if event_count < 3 and avg_size < 10:
            return True
        return False

    async def _detect_correlation_risk(self, trade: Trade) -> str | None:
        from app.models.portfolio import MarketCorrelation
        if not trade.market_id:
            return None
        result = await self.db.execute(
            select(MarketCorrelation)
            .where(
                (MarketCorrelation.market_a_id == trade.market_id) |
                (MarketCorrelation.market_b_id == trade.market_id)
            )
            .where(MarketCorrelation.correlation_coefficient >= 0.8)
            .order_by(MarketCorrelation.correlation_coefficient.desc())
            .limit(1)
        )
        corr = result.scalar_one_or_none()
        if corr:
            return f"correlation={float(corr.correlation_coefficient):.2f}"
        return None

    async def close_trade_via_exit(self, trade: Trade, exit_price: float) -> None:
        from app.services.trade_service import TradeService
        async with self.db.bind.connect() as conn:
            pass
        service = TradeService(self.db)
        await service.close_trade(trade.id, exit_price=exit_price)

    def get_exit_reason_distribution(self) -> dict[str, int]:
        return dict(self._exits_by_reason)

    def get_forced_exit_rate(self) -> float:
        total = sum(self._exits_by_reason.values())
        return self._forced_exit_count / total if total > 0 else 0.0

    def reset_stats(self):
        self._exits_by_reason = {}
        self._forced_exit_count = 0
