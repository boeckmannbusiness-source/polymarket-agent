import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.shadow.dashboard_service import DashboardService
from app.schemas.shadow import StrategyScorecard, ScorecardMetrics
from datetime import datetime

@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_dashboard_generation(mock_db):
    service = DashboardService(mock_db)

    # Mock global scorecard
    metrics = ScorecardMetrics(decision_count=100, replay_parity=0.98, brier_score=0.1, win_rate=0.6, realized_ev=50.0)
    mock_scorecard = StrategyScorecard(
        strategy_id="GLOBAL",
        global_metrics=metrics,
        rolling_7d=metrics,
        rolling_30d=metrics
    )
    service.scorecard_engine.generate_scorecard = AsyncMock(return_value=mock_scorecard)

    # Mock strategy list
    mock_strat_res = MagicMock()
    mock_strat_res.scalars.return_value.all.return_value = ["strat1"]
    mock_db.execute.return_value = mock_strat_res

    # Mock audit and stability
    service.audit_service.audit_strategy = AsyncMock(return_value={
        "status": "READY",
        "metrics": metrics.model_dump(),
        "timestamp": datetime.now().isoformat(),
        "thresholds": {},
        "reasons": []
    })
    service.stability_monitor.check_stability = AsyncMock(return_value=[])

    report = await service.generate_ops_report()

    assert "# SHADOW_OPERATIONS_REPORT" in report
    assert "strat1" in report
    assert "READY" in report
    assert os.path.exists("SHADOW_OPERATIONS_REPORT.md")

@pytest.mark.asyncio
async def test_dashboard_consistency(mock_db):
    service = DashboardService(mock_db)

    # Verify that it handles empty strategies
    mock_strat_res = MagicMock()
    mock_strat_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_strat_res

    metrics = ScorecardMetrics()
    service.scorecard_engine.generate_scorecard = AsyncMock(return_value=StrategyScorecard(
        strategy_id="GLOBAL", global_metrics=metrics, rolling_7d=metrics, rolling_30d=metrics
    ))

    report = await service.generate_ops_report()
    assert "Total Decisions | 0" in report
