from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Market, MarketEvent, Signal, SignalOutcome
from app.models.portfolio import PortfolioSnapshot
from app.models.market_snapshot import MarketStateSnapshot
from app.strategies import get_strategy_names
from app.services.signal_evaluation_service import SignalEvaluationService
from app.services.global_risk_guard import GlobalRiskGuard
from app.services.safety_service import SafetyService
from app.schemas.agent import (
    AgentPortfolioSnapshot,
    AgentStrategyPerformanceItem,
    AgentSignalDistribution,
    AgentMarketState,
    AgentRiskState,
    AgentFullSnapshot,
)


_LONG_DIRECTIONS = {"bullish", "buy_yes"}
_SHORT_DIRECTIONS = {"bearish", "buy_no"}


class AgentSnapshotService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_portfolio(self) -> AgentPortfolioSnapshot:
        result = await self.db.execute(
            select(PortfolioSnapshot)
            .order_by(desc(PortfolioSnapshot.timestamp))
            .limit(2)
        )
        snapshots = list(result.scalars().all())

        latest = snapshots[0] if snapshots else None
        prev = snapshots[1] if len(snapshots) > 1 else None

        if latest and latest.portfolio_value is not None:
            total_equity = float(latest.portfolio_value)
        else:
            total_equity = float(settings.PAPER_INITIAL_CAPITAL)

        exposure = float(latest.total_exposure or 0) if latest else 0.0
        cash_balance = max(0.0, total_equity - exposure)

        pnl_total = (
            float(latest.total_unrealized_pnl or 0) + float(latest.total_realized_pnl or 0)
        ) if latest else 0.0

        if latest and prev and prev.portfolio_value is not None:
            pnl_24h = total_equity - float(prev.portfolio_value)
        else:
            pnl_24h = 0.0

        return AgentPortfolioSnapshot(
            total_equity=round(total_equity, 2),
            cash_balance=round(cash_balance, 2),
            exposure=round(exposure, 2),
            pnl_24h=round(pnl_24h, 2),
            pnl_total=round(pnl_total, 2),
        )

    async def get_strategies(self) -> list[AgentStrategyPerformanceItem]:
        names = get_strategy_names()
        eval_service = SignalEvaluationService(self.db)
        cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)

        items: list[AgentStrategyPerformanceItem] = []
        for name in names:
            try:
                pnl_result = await self.db.execute(
                    select(func.coalesce(func.sum(SignalOutcome.pnl_close), 0))
                    .where(
                        SignalOutcome.strategy_name == name,
                        SignalOutcome.entry_timestamp >= cutoff_24h,
                    )
                )
                pnl_24h = float(pnl_result.scalar() or 0)

                summary = await eval_service.get_strategy_summary(name)
                total_pnl = float(summary.get("total_pnl", 0) or 0)
                win_rate = float(summary["win_rate"]) if summary.get("win_rate") is not None else None
                sharpe = float(summary["sharpe_ratio"]) if summary.get("sharpe_ratio") is not None else None
                num_trades = int(summary.get("total_signals", 0))

                items.append(AgentStrategyPerformanceItem(
                    name=name,
                    pnl_24h=round(pnl_24h, 4),
                    pnl_total=round(total_pnl, 4),
                    win_rate=round(win_rate, 4) if win_rate is not None else None,
                    num_trades=num_trades,
                    sharpe_ratio=round(sharpe, 4) if sharpe is not None else None,
                ))
            except Exception:
                items.append(AgentStrategyPerformanceItem(
                    name=name,
                    pnl_24h=0.0,
                    pnl_total=0.0,
                    win_rate=None,
                    num_trades=0,
                    sharpe_ratio=None,
                ))

        return items

    async def get_market_state(self) -> AgentMarketState:
        result = await self.db.execute(
            select(func.count(Market.id)).where(Market.resolved == False)
        )
        active_count = result.scalar() or 0

        liquidity_result = await self.db.execute(
            select(func.coalesce(func.avg(Market.liquidity), 0))
            .where(Market.resolved == False, Market.liquidity.isnot(None))
        )
        avg_liquidity = float(liquidity_result.scalar() or 0)

        volatility_index: float | None = None
        try:
            vol_result = await self.db.execute(
                select(func.avg(MarketStateSnapshot.volatility))
                .where(MarketStateSnapshot.volatility.isnot(None))
            )
            vol_val = vol_result.scalar()
            if vol_val is not None:
                volatility_index = round(float(vol_val), 6)
        except Exception:
            pass

        long_count = 0
        short_count = 0
        neutral_count = 0

        signal_result = await self.db.execute(
            select(Signal.direction, func.count(Signal.id))
            .where(Signal.is_active == True)
            .group_by(Signal.direction)
        )
        for direction, count in signal_result.all():
            dir_key = (direction or "").lower().strip()
            if dir_key in _LONG_DIRECTIONS:
                long_count += count
            elif dir_key in _SHORT_DIRECTIONS:
                short_count += count
            else:
                neutral_count += count

        return AgentMarketState(
            active_markets_count=active_count,
            volatility_index=volatility_index,
            liquidity_score=round(avg_liquidity, 2) if avg_liquidity else None,
            signal_distribution=AgentSignalDistribution(
                long=long_count,
                short=short_count,
                neutral=neutral_count,
            ),
        )

    async def get_risk_state(self) -> AgentRiskState:
        alerts: list[str] = []

        snap_result = await self.db.execute(
            select(PortfolioSnapshot)
            .order_by(desc(PortfolioSnapshot.timestamp))
            .limit(1)
        )
        latest_snap = snap_result.scalar_one_or_none()
        max_drawdown_pct = (float(latest_snap.drawdown or 0) * 100) if latest_snap else 0.0

        guard = GlobalRiskGuard(self.db)
        exposure = await guard.get_exposure_summary()
        exposure_utilization = float(exposure.get("exposure_utilization_pct", 0))

        safety = SafetyService(self.db)
        safety_state = await safety.get_state()

        cutoff_10m = datetime.now(timezone.utc) - timedelta(minutes=10)
        event_result = await self.db.execute(
            select(func.count())
            .select_from(MarketEvent)
            .where(MarketEvent.timestamp >= cutoff_10m)
        )
        recent_events = event_result.scalar() or 0

        if safety_state.get("kill_switch_active"):
            alerts.append("Kill switch is active")

        if safety_state.get("circuit_breaker_active"):
            alerts.append(f"Circuit breaker: {safety_state.get('circuit_breaker_reason', 'active')}")

        quarantined = safety_state.get("quarantined_strategies", [])
        if quarantined:
            alerts.append(f"Quarantined strategies: {', '.join(quarantined)}")

        if recent_events == 0:
            alerts.append("No market events in last 10 minutes")

        if max_drawdown_pct > 15:
            alerts.append(f"Portfolio drawdown at {max_drawdown_pct:.1f}%")

        if exposure_utilization > 80:
            alerts.append(f"Exposure utilization at {exposure_utilization:.0f}%")

        if (safety_state.get("kill_switch_active")
                or safety_state.get("circuit_breaker_active")
                or max_drawdown_pct > 20):
            risk_level: str = "high"
        elif (recent_events == 0
              or max_drawdown_pct > 10
              or bool(quarantined)
              or exposure_utilization > 80):
            risk_level = "medium"
        else:
            risk_level = "low"

        return AgentRiskState(
            risk_level=risk_level,
            max_drawdown=round(max_drawdown_pct, 2),
            exposure_utilization_pct=round(exposure_utilization, 1),
            active_risk_alerts=alerts,
        )

    async def get_full_snapshot(self) -> AgentFullSnapshot:
        portfolio = await self.get_portfolio()
        strategies = await self.get_strategies()
        market = await self.get_market_state()
        risk = await self.get_risk_state()

        return AgentFullSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            portfolio=portfolio,
            strategies=strategies,
            market=market,
            risk=risk,
        )
