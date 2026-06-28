import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.services.shadow.stability_monitor import StrategyStabilityMonitor
from app.schemas.shadow import StrategyScorecard, ScorecardMetrics

@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_ev_degradation(mock_db):
    monitor = StrategyStabilityMonitor(mock_db)

    # Mock global good, recent bad
    global_metrics = ScorecardMetrics(decision_count=100, realized_ev=50.0) # avg 0.5
    recent_metrics = ScorecardMetrics(decision_count=10, realized_ev=-1.0) # avg -0.1

    mock_scorecard = StrategyScorecard(
        strategy_id="strat1",
        global_metrics=global_metrics,
        rolling_7d=recent_metrics,
        rolling_30d=global_metrics
    )

    monitor.scorecard_engine.generate_scorecard = AsyncMock(return_value=mock_scorecard)

    receipts = await monitor.check_stability("strat1")
    assert any(r.metric == "realized_ev" and r.severity == "HIGH" for r in receipts)

@pytest.mark.asyncio
async def test_confidence_drift(mock_db):
    monitor = StrategyStabilityMonitor(mock_db)

    # Mock high drift in recent
    global_metrics = ScorecardMetrics(decision_count=100, confidence_drift=0.1)
    recent_metrics = ScorecardMetrics(decision_count=10, confidence_drift=0.4)

    mock_scorecard = StrategyScorecard(
        strategy_id="strat1",
        global_metrics=global_metrics,
        rolling_7d=recent_metrics,
        rolling_30d=global_metrics
    )

    monitor.scorecard_engine.generate_scorecard = AsyncMock(return_value=mock_scorecard)

    receipts = await monitor.check_stability("strat1")
    assert any(r.metric == "confidence_drift" for r in receipts)

@pytest.mark.asyncio
async def test_stability_detection(mock_db):
    monitor = StrategyStabilityMonitor(mock_db)

    # Mock stable metrics
    metrics = ScorecardMetrics(
        decision_count=100,
        realized_ev=50.0,
        confidence_drift=0.1,
        replay_parity=0.98
    )

    mock_scorecard = StrategyScorecard(
        strategy_id="strat1",
        global_metrics=metrics,
        rolling_7d=metrics,
        rolling_30d=metrics
    )

    monitor.scorecard_engine.generate_scorecard = AsyncMock(return_value=mock_scorecard)

    receipts = await monitor.check_stability("strat1")
    assert len(receipts) == 0
