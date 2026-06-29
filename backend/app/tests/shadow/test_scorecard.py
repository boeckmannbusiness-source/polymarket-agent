import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from collections import namedtuple

from app.services.shadow.scorecard_engine import ScorecardEngine
from app.models.shadow_decision_log import ShadowDecisionLog
from app.schemas.shadow import StrategyScorecard

# Helper to mock Row result
ScorecardRow = namedtuple("ScorecardRow", [
    "total_decisions", "total_resolved", "total_closed", "sum_realized_ev", "sum_expected_ev",
    "win_count", "replay_matches", "rejected_count", "sum_brier_err",
    "sum_cal_err", "avg_confidence", "conf_count"
])

@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_scorecard_generation(mock_db):
    engine = ScorecardEngine(mock_db)

    # Mock row data
    row = ScorecardRow(
        total_decisions=1, total_resolved=1, total_closed=1, sum_realized_ev=1.0, sum_expected_ev=0.5,
        win_count=1, replay_matches=1, rejected_count=0, sum_brier_err=0.04,
        sum_cal_err=0.2, avg_confidence=0.8, conf_count=1
    )

    mock_result = MagicMock()
    mock_result.fetchone.return_value = row
    mock_db.execute.return_value = mock_result

    scorecard = await engine.generate_scorecard("strat1")

    assert isinstance(scorecard, StrategyScorecard)
    assert scorecard.strategy_id == "strat1"
    assert scorecard.global_metrics.decision_count == 1
    assert scorecard.global_metrics.win_rate == 1.0
    assert scorecard.global_metrics.replay_parity == 1.0

@pytest.mark.asyncio
async def test_strategy_partitioning(mock_db):
    engine = ScorecardEngine(mock_db)

    row = ScorecardRow(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    mock_result = MagicMock()
    mock_result.fetchone.return_value = row
    mock_db.execute.return_value = mock_result

    await engine.generate_scorecard("strat_A")

    # Verify first call (global metrics)
    call_args = mock_db.execute.call_args_list[0]
    query = call_args[0][0]
    assert "strat_A" in str(query.compile(compile_kwargs={"literal_binds": True}))

@pytest.mark.asyncio
async def test_rolling_metrics(mock_db):
    engine = ScorecardEngine(mock_db)

    row_global = ScorecardRow(2, 2, 2, 0.3, 0.0, 1, 0, 0, 0.16, 0.4, 0.5, 2)
    row_rolling = ScorecardRow(1, 1, 1, 0.5, 0.0, 1, 0, 0, 0.16, 0.4, 0.6, 1)

    def side_effect(query):
        mock_res = MagicMock()
        q_str = str(query.compile(compile_kwargs={"literal_binds": True}))
        if " >= '" in q_str:
            mock_res.fetchone.return_value = row_rolling
        else:
            mock_res.fetchone.return_value = row_global
        return mock_res

    mock_db.execute.side_effect = side_effect

    scorecard = await engine.generate_scorecard("strat1")

    assert scorecard.global_metrics.decision_count == 2
    assert scorecard.rolling_7d.decision_count == 1
    assert scorecard.rolling_30d.decision_count == 1
