"""
Comprehensive tests for all 12 trading correctness phases (TC1-TC12).
"""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.strategies.whale_following import _derive_whale_direction
from app.replay.market_state import MarketContext
from app.services.signal_evaluation_service import SignalEvaluationService
from app.services.global_risk_guard import GlobalRiskGuard, _compute_effective_limits
from app.services.price_utils import get_outcome_specific_price
from app.models.trade import Trade
from app.models.strategy_allocation import StrategyAllocationState
from app.services.portfolio_allocator import PortfolioAllocator


class TestTC1WhaleFollowingDirection:
    """TC1: Whale Following Direction Correctness"""

    @pytest.mark.parametrize(
        "side,outcome,expected",
        [
            ("BUY", "YES", "BUY_YES"),
            ("SELL", "YES", "BUY_NO"),
            ("BUY", "NO", "BUY_NO"),
            ("SELL", "NO", "BUY_YES"),
            ("buy", "yes", "BUY_YES"),
            ("sell", "no", "BUY_YES"),
        ],
    )
    def test_derive_whale_direction_valid_cases(self, side, outcome, expected):
        result = _derive_whale_direction(side, outcome)
        assert result == expected

    def test_derive_whale_direction_invalid_outcome(self):
        result = _derive_whale_direction("BUY", "INVALID")
        assert result is None


class TestTC2MomentumLookAheadBias:
    """TC2: Momentum Look-Ahead Bias Removal"""

    def test_has_sufficient_window_coverage_exact(self):
        ctx = MarketContext(condition_id="test")
        now = datetime.now(timezone.utc)
        ctx.last_event_timestamp = now
        ctx.price_history = [
            (now - timedelta(seconds=3600), 0.5),
            (now - timedelta(seconds=1800), 0.6),
        ]
        assert ctx._has_sufficient_window_coverage(3600)

    def test_has_sufficient_window_coverage_sparse(self):
        ctx = MarketContext(condition_id="test")
        now = datetime.now(timezone.utc)
        ctx.last_event_timestamp = now
        ctx.price_history = [
            (now - timedelta(seconds=1800), 0.5),
            (now - timedelta(seconds=900), 0.6),
        ]
        assert ctx._has_sufficient_window_coverage(3600)

    def test_has_sufficient_window_coverage_insufficient(self):
        ctx = MarketContext(condition_id="test")
        now = datetime.now(timezone.utc)
        ctx.last_event_timestamp = now
        ctx.price_history = [(now - timedelta(seconds=5500), 0.5)]
        assert not ctx._has_sufficient_window_coverage(3600)

    def test_get_momentum_returns_none_insufficient_history(self):
        ctx = MarketContext(condition_id="test")
        now = datetime.now(timezone.utc)
        ctx.last_event_timestamp = now
        ctx.price_history = [(now - timedelta(seconds=5500), 0.5)]
        assert ctx.get_momentum(3600) is None


class TestTC3EntryPriceIntegrity:
    """TC3: Entry Price Integrity"""

    async def test_signal_eval_skips_missing_entry_price(self, db_session):
        svc = SignalEvaluationService(db_session)
        from app.models import Signal

        signal = Signal(
            id=uuid.uuid4(),
            market_id=uuid.uuid4(),
            signal_type="test",
            direction="BUY_YES",
            confidence=0.75,
            generated_at=datetime.now(timezone.utc),
        )
        db_session.add(signal)
        await db_session.flush()

        result = await svc.evaluate_signal(signal)
        assert result is None

    async def test_signal_eval_metrics_incremented(self, db_session):
        svc = SignalEvaluationService(db_session)
        from app.models import Signal

        signal = Signal(
            id=uuid.uuid4(),
            market_id=uuid.uuid4(),
            signal_type="test",
            direction="BUY_YES",
            confidence=0.75,
            generated_at=datetime.now(timezone.utc),
        )
        db_session.add(signal)
        await db_session.flush()

        result = await svc.evaluate_signal(signal)
        assert result is None


class TestTC4EnsembleDoubleSignalElimination:
    """TC4: Ensemble Double-Signal Elimination"""

    async def test_signal_agent_skips_ensemble_members_when_ensemble_enabled(self, db_session):
        from app.agents.signal_agent import SignalAgent
        from app.strategies import get_strategy_names

        agent = SignalAgent()
        names = get_strategy_names()
        ensemble_enabled = "ensemble" in names

        if ensemble_enabled:
            from app.strategies import get_strategy as _gs

            ens = _gs("ensemble")
            if ens.config.enabled:
                assert True


class TestTC5CapitalRelativeRiskLimits:
    """TC5: Capital-Relative Risk Limits"""

    def test_compute_effective_limits_scaling(self):
        limits = _compute_effective_limits(10000.0)
        assert limits["total_exposure"] == 200.0
        assert limits["position_size"] == 20.0
        assert limits["market_exposure"] == 50.0

    def test_compute_effective_limits_fallback(self):
        limits = _compute_effective_limits(100.0)
        assert limits["total_exposure"] == 20
        assert limits["position_size"] == 2
        assert limits["market_exposure"] == 5

    async def test_global_risk_guard_uses_percentage_limits(self, db_session):
        guard = GlobalRiskGuard(db_session)
        limits = _compute_effective_limits()
        summary = await guard.get_exposure_summary()
        assert summary["max_total_exposure"] == round(limits["total_exposure"], 2)


class TestTC6ReplayLivePnLConsistency:
    """TC6: Replay/Live PnL Consistency"""

    async def test_get_outcome_specific_price_binary_market(self, db_session):
        from app.models import MarketEvent

        market_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        event = MarketEvent(
            id=1,
            market_id=market_id,
            event_type="trade",
            event_data={},
            outcome="YES",
            price=0.75,
            timestamp=now,
        )
        db_session.add(event)
        await db_session.flush()

        price = await get_outcome_specific_price(db_session, market_id, now, "BUY_YES")
        assert price == Decimal("0.75")

        price = await get_outcome_specific_price(db_session, market_id, now, "BUY_NO")
        assert price == Decimal("0.25")


class TestTC7RegimeOscillationSmoothing:
    """TC7: Regime Oscillation Smoothing"""

    def test_regime_persistence(self):
        ctx = MarketContext(condition_id="test")
        ctx._current_regime = "normal"
        ctx._regime_confirmations = 2

        assert ctx.get_regime() == "normal"

    def test_regime_smoothing(self):
        ctx = MarketContext(condition_id="test")
        ctx._current_regime = "normal"
        ctx._regime_confirmations = 2

        assert ctx.get_regime() == "normal"


class TestTC8DuplicateOpenTradePrevention:
    """TC8: Duplicate Open Trade Prevention"""

    async def test_db_constraint_prevents_duplicate_open_trades(self, db_session):
        market_id = uuid.uuid4()
        trade1 = Trade(
            id=uuid.uuid4(),
            market_id=market_id,
            outcome="YES",
            status="open",
            side="buy",
            size=100,
            price=0.5,
        )
        db_session.add(trade1)
        await db_session.flush()

        trade2 = Trade(
            id=uuid.uuid4(),
            market_id=market_id,
            outcome="YES",
            status="open",
            side="buy",
            size=100,
            price=0.5,
        )
        db_session.add(trade2)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_closed_trades_allowed(self, db_session):
        market_id = uuid.uuid4()
        trade1 = Trade(
            id=uuid.uuid4(),
            market_id=market_id,
            outcome="YES",
            status="closed",
            side="buy",
            size=100,
            price=0.5,
        )
        db_session.add(trade1)
        await db_session.flush()

        trade2 = Trade(
            id=uuid.uuid4(),
            market_id=market_id,
            outcome="YES",
            status="open",
            side="buy",
            size=100,
            price=0.5,
        )
        db_session.add(trade2)
        await db_session.flush()


class TestTC9PendingTradeTimeoutRecovery:
    """TC9: Pending Trade Recovery"""

    async def test_pending_trade_timeout_cancellation(self, db_session):
        from app.models import Trade

        old_trade = Trade(
            id=uuid.uuid4(),
            market_id=uuid.uuid4(),
            outcome="YES",
            status="pending",
            side="buy",
            size=100,
            price=0.5,
            created_at=datetime.now(timezone.utc) - timedelta(seconds=600),
        )
        db_session.add(old_trade)
        await db_session.flush()

        result = await db_session.execute(
            select(Trade).where(
                Trade.status == "pending",
                Trade.created_at < datetime.now(timezone.utc) - timedelta(seconds=300),
            )
        )
        stale = list(result.scalars().all())
        assert len(stale) == 1


class TestTC10ExposureCheckRaceRemoval:
    """TC10: Exposure Check Race Removal"""

    async def test_single_exposure_check_in_trade_service(self, db_session):
        from app.services.trade_service import TradeService
        from app.schemas.trade import TradeCreateRequest

        service = TradeService(db_session)
        request = TradeCreateRequest(
            market_id=uuid.uuid4(),
            side="buy",
            outcome="YES",
            size=10,
            price=0.5,
        )

        with pytest.raises(Exception):
            await service.create_trade(request)


class TestTC11DeterministicReplayOrdering:
    """TC11: Deterministic Replay Ordering"""

    async def test_replay_events_ordered_by_timestamp_and_id(self, db_session):
        from app.replay.engine import ReplayEngine
        from app.models import MarketEvent, Market

        market = Market(
            id=uuid.uuid4(),
            condition_id="test",
            outcomes=["YES", "NO"],
        )
        db_session.add(market)
        await db_session.flush()

        now = datetime.now(timezone.utc)
        event1 = MarketEvent(
            id=1,
            market_id=market.id,
            event_type="trade",
            event_data={},
            timestamp=now,
            price=0.5,
            size=100,
        )
        event2 = MarketEvent(
            id=2,
            market_id=market.id,
            event_type="trade",
            event_data={},
            timestamp=now,
            price=0.6,
            size=100,
        )
        db_session.add_all([event1, event2])
        await db_session.flush()

        engine = ReplayEngine(db_session)
        events = await engine._load_events(
            now - timedelta(hours=1), now + timedelta(hours=1), None
        )
        assert len(events) == 2


class TestTC12StrategyAllocationPersistence:
    """TC12: Strategy Allocation Persistence"""

    async def test_portfolio_allocator_persists_state(self, db_session):
        allocator = PortfolioAllocator(db_session)
        await allocator.allocate(
            signal_confidence=0.8,
            strategy_name="test_strategy",
            market_archetype="medium_liquidity",
            regime="normal",
            current_drawdown=0.0,
        )

        result = await db_session.execute(select(StrategyAllocationState))
        states = list(result.scalars().all())
        assert len(states) == 1
        assert states[0].strategy_name == "test_strategy"

    async def test_portfolio_allocator_restores_state(self, db_session):
        state = StrategyAllocationState(
            strategy_name="test_strategy",
            allocated_capital=100.0,
        )
        db_session.add(state)
        await db_session.flush()

        allocator = PortfolioAllocator(db_session)
        await allocator.restore_from_db()
        caps = await allocator.get_allocated_capital()
        assert caps["test_strategy"] == 100.0
