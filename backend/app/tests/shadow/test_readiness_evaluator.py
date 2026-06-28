import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from app.services.shadow.readiness_evaluator import PromotionReadinessEvaluator

@pytest.mark.asyncio
async def test_not_ready_zero_data():
    db = AsyncMock()
    evaluator = PromotionReadinessEvaluator(db)

    # Mock evaluator.evaluate_strategy to return empty metrics
    evaluator.evaluator.evaluate_strategy = AsyncMock(return_value={
        "strategy_id": "s1",
        "total_decisions": 0,
        "realized_ev": 0.0,
        "brier_score": 0.0,
        "win_rate": 0.0
    })
    evaluator.evaluator.get_global_metrics = AsyncMock(return_value={
        "replay_parity": 0.0,
        "certification_violations": 0
    })

    result = await evaluator.evaluate_readiness("s1")

    assert result["status"] == "NOT_READY"
    assert any("Insufficient decision volume" in r for r in result["blocking_reasons"])
    assert any("Positive realized EV required" in r for r in result["blocking_reasons"])

@pytest.mark.asyncio
async def test_readiness_thresholds():
    db = AsyncMock()
    evaluator = PromotionReadinessEvaluator(db)

    # Mock near-ready metrics
    evaluator.evaluator.evaluate_strategy = AsyncMock(return_value={
        "strategy_id": "s1",
        "total_decisions": 501,
        "realized_ev": 10.5,
        "brier_score": 0.26, # Just over 0.25
        "win_rate": 0.5
    })
    evaluator.evaluator.get_global_metrics = AsyncMock(return_value={
        "replay_parity": 0.96,
        "certification_violations": 0
    })

    result = await evaluator.evaluate_readiness("s1")
    assert result["status"] == "NOT_READY"
    assert any("Brier Score" in r for r in result["blocking_reasons"])

@pytest.mark.asyncio
async def test_policy_driven_evaluation():
    db = AsyncMock()
    evaluator = PromotionReadinessEvaluator(db)

    # Mock ready metrics
    evaluator.evaluator.evaluate_strategy = AsyncMock(return_value={
        "strategy_id": "s1",
        "total_decisions": 600,
        "realized_ev": 50.0,
        "brier_score": 0.15,
        "win_rate": 0.6
    })
    evaluator.evaluator.get_global_metrics = AsyncMock(return_value={
        "replay_parity": 0.98,
        "certification_violations": 0
    })

    result = await evaluator.evaluate_readiness("s1")
    assert result["status"] == "READY"
    assert len(result["blocking_reasons"]) == 0
    assert result["progress"]["decision_volume"] == "600/500"
