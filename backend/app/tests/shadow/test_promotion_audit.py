import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.shadow.promotion_audit_service import PromotionAuditService
from app.schemas.shadow import StrategyScorecard, ScorecardMetrics

@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_policy_threshold_enforcement(mock_db):
    service = PromotionAuditService(mock_db)

    # Mock ready metrics
    ready_metrics = ScorecardMetrics(
        decision_count=600,
        replay_parity=0.98,
        realized_ev=10.0,
        brier_score=0.15
    )

    mock_scorecard = StrategyScorecard(
        strategy_id="strat1",
        global_metrics=ready_metrics,
        rolling_7d=ready_metrics,
        rolling_30d=ready_metrics
    )

    service.scorecard_engine.generate_scorecard = AsyncMock(return_value=mock_scorecard)

    # Mock violation check
    mock_violation_res = MagicMock()
    mock_violation_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_violation_res

    audit = await service.audit_strategy("strat1")
    assert audit["status"] == "READY"
    assert len(audit["reasons"]) == 0

@pytest.mark.asyncio
async def test_not_ready_reason_generation(mock_db):
    service = PromotionAuditService(mock_db)

    # Mock failing metrics
    failing_metrics = ScorecardMetrics(
        decision_count=100, # Too low
        replay_parity=0.90, # Too low
        realized_ev=-5.0,   # Negative
        brier_score=0.40    # Too high
    )

    mock_scorecard = StrategyScorecard(
        strategy_id="strat1",
        global_metrics=failing_metrics,
        rolling_7d=failing_metrics,
        rolling_30d=failing_metrics
    )

    service.scorecard_engine.generate_scorecard = AsyncMock(return_value=mock_scorecard)

    # Mock violation check
    mock_violation_res = MagicMock()
    mock_violation_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_violation_res

    audit = await service.audit_strategy("strat1")
    assert audit["status"] == "NOT_READY"
    assert len(audit["reasons"]) == 4
    assert any("Insufficient decision volume" in r for r in audit["reasons"])
    assert any("Replay parity below threshold" in r for r in audit["reasons"])
    assert any("Positive realized EV required" in r for r in audit["reasons"])
    assert any("Confidence calibration unstable" in r for r in audit["reasons"])

@pytest.mark.asyncio
async def test_policy_reload(mock_db):
    service = PromotionAuditService(mock_db)

    with patch("app.services.shadow.promotion_audit_service.parse_promotion_policy") as mock_parse:
        mock_parse.return_value = {"min_decisions": 1000}

        metrics = ScorecardMetrics(decision_count=600)
        service.scorecard_engine.generate_scorecard = AsyncMock(return_value=StrategyScorecard(
            strategy_id="s1", global_metrics=metrics, rolling_7d=metrics, rolling_30d=metrics
        ))

        mock_violation_res = MagicMock()
        mock_violation_res.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_violation_res

        audit = await service.audit_strategy("strat1")
        assert audit["status"] == "NOT_READY"
        assert any("1000" in r for r in audit["reasons"])

        mock_parse.assert_called_once()
