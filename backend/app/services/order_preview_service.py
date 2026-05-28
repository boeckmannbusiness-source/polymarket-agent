from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Signal, Trade
from app.services.global_risk_guard import GlobalRiskGuard
from app.services.risk_overlay import RiskOverlay
from app.services.strategy_guardian import StrategyGuardian
from app.services.exit_engine import ExitEngine
from app.services.portfolio_allocator import PortfolioAllocator
from app.services.execution_simulator import ExecutionSimulator
from app.services.edge_reality_engine import EdgeRealityEngine
from app.config import settings
from app.services.trade_service import FORCE_TRADING_DISABLED, MICRO_LIVE_SAFE_MODE


@dataclass
class OrderPreview:
    signal_id: str | None
    strategy: str
    confidence: float
    weighted_confidence: float
    market_archetype: str
    price_zone: str
    regime: str
    liquidity: float
    volatility: float
    spread: float
    sizing_factors: dict[str, Any]
    approved: bool
    approval_reason: str | None
    rejection_reason: str | None
    expected_risk: float
    expected_reward: float
    exit_thresholds: dict[str, Any]
    guardian_state: dict[str, Any]
    overlay_state: dict[str, Any]
    previewed_at: str


class OrderPreviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def preview(self, signal_id: str) -> OrderPreview:
        result = await self.db.execute(
            select(Signal).where(Signal.id == signal_id)
        )
        signal = result.scalar_one_or_none()

        if not signal:
            return OrderPreview(
                signal_id=signal_id,
                strategy="unknown",
                confidence=0.0,
                weighted_confidence=0.0,
                market_archetype="unknown",
                price_zone="unknown",
                regime="unknown",
                liquidity=0.0,
                volatility=0.0,
                spread=0.0,
                sizing_factors={},
                approved=False,
                approval_reason=None,
                rejection_reason=f"signal_{signal_id}_not_found",
                expected_risk=0.0,
                expected_reward=0.0,
                exit_thresholds={},
                guardian_state={},
                overlay_state={},
                previewed_at=datetime.now(timezone.utc).isoformat(),
            )

        confidence = float(signal.confidence)
        strategy = signal.source_agent or "unknown"
        market_archetype = "medium_liquidity"
        price_zone = "mid"
        regime = "normal"

        guardian = StrategyGuardian(self.db)
        guardian_state = await guardian.get_state(strategy)

        overlay = RiskOverlay(self.db)
        overlay_state = await overlay.check()

        allocator = PortfolioAllocator(self.db)
        allocation = await allocator.allocate(
            signal_confidence=confidence,
            strategy_name=strategy,
            market_archetype=market_archetype,
            regime=regime,
            current_drawdown=0.0,
        )

        sim = ExecutionSimulator()
        slippage = sim.estimate_dynamic_slippage(
            liquidity=1.0,
            spread=0.01,
            volatility=0.02,
            order_size=allocation.size,
            market_archetype=market_archetype,
        )

        edge_engine = EdgeRealityEngine(self.db)
        edge = await edge_engine.compute_edge(strategy, days=60)

        exit_engine = ExitEngine(self.db)
        exit_decisions = ""
        for trade_id in []:
            decisions = await exit_engine.evaluate_exit(trade_id)
            exit_decisions = str(decisions)

        guard = GlobalRiskGuard(self.db)
        exposure = await guard.get_exposure_summary()

        sizing_factors = {
            "base_size": allocation.size,
            "confidence_factor": confidence,
            "regime_factor": 1.0,
            "drawdown_factor": 1.0,
            "liquidity_factor": 1.0,
            "max_cap": allocation.size,
        }

        rejection_reasons: list[str] = []

        if FORCE_TRADING_DISABLED:
            rejection_reasons.append("kill_switch_active")

        if overlay_state.status == "MARKET_DATA_UNSTABLE":
            rejection_reasons.append("market_data_unstable")
        elif overlay_state.status == "STOPPED":
            rejection_reasons.append(f"overlay_stopped:{overlay_state.reason}")
        elif overlay_state.status == "REDUCED":
            rejection_reasons.append(f"overlay_reduced:{overlay_state.reason}")

        if guardian_state.get("status") == "DISABLE":
            rejection_reasons.append("strategy_disabled_by_guardian")

        existing = await self.db.execute(
            select(Trade).where(
                Trade.signal_id == signal_id,
                Trade.status.in_(["open", "pending"]),
            )
        )
        if existing.scalar_one_or_none():
            rejection_reasons.append("signal_already_executed")

        open_result = await self.db.execute(
            select(Trade).where(
                Trade.market_id == signal.market_id,
                Trade.outcome == signal.direction.upper(),
                Trade.status.in_(["open", "pending"]),
            )
        )
        if open_result.scalar_one_or_none():
            rejection_reasons.append("duplicate_market_position")

        exposure_check = await guard.check_exposure(
            market_id=str(signal.market_id),
            outcome=signal.direction.upper(),
            proposed_size=float(allocation.size),
            proposed_price=float(signal.implied_probability or 0),
        )
        if not exposure_check.approved:
            rejection_reasons.append(f"exposure_limit:{exposure_check.reason}")

        approved = len(rejection_reasons) == 0

        expected_risk = allocation.size * slippage
        expected_reward = allocation.size * abs(edge.expectancy) if edge.expectancy > 0 else 0.0

        exit_thresholds = {
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.15,
            "max_hold_hours": 72,
        }

        return OrderPreview(
            signal_id=signal_id,
            strategy=strategy,
            confidence=confidence,
            weighted_confidence=confidence * 0.8,
            market_archetype=market_archetype,
            price_zone=price_zone,
            regime=regime,
            liquidity=0.8,
            volatility=0.02,
            spread=0.01,
            sizing_factors=sizing_factors,
            approved=approved,
            approval_reason="all_checks_passed" if approved else None,
            rejection_reason=";".join(rejection_reasons) if rejection_reasons else None,
            expected_risk=round(expected_risk, 6),
            expected_reward=round(expected_reward, 6),
            exit_thresholds=exit_thresholds,
            guardian_state={
                "status": guardian_state.get("status", "UNKNOWN"),
                "reason": guardian_state.get("reason", ""),
            },
            overlay_state={
                "status": overlay_state.status,
                "reason": overlay_state.reason,
            },
            previewed_at=datetime.now(timezone.utc).isoformat(),
        )
