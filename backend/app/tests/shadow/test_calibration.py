import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from app.services.shadow.outcome_evaluator import OutcomeEvaluator
from app.models.shadow_decision_log import ShadowDecisionLog

@pytest.mark.asyncio
async def test_brier_score():
    db = AsyncMock()
    evaluator = OutcomeEvaluator(db)

    # Setup mock decisions
    # Dec 1: Conf 0.8, Win (1.0) -> Error^2 = (0.8-1.0)^2 = 0.04
    # Dec 2: Conf 0.6, Loss (0.0) -> Error^2 = (0.6-0.0)^2 = 0.36
    # Avg Brier = (0.04 + 0.36) / 2 = 0.20

    dec1 = ShadowDecisionLog(
        id=uuid.uuid4(),
        strategy_id="strat1",
        confidence=0.8,
        actual_ev=10.0,
        simulated_exit_price=0.6
    )
    dec2 = ShadowDecisionLog(
        id=uuid.uuid4(),
        strategy_id="strat1",
        confidence=0.6,
        actual_ev=-5.0,
        simulated_exit_price=0.4
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [dec1, dec2]
    db.execute.return_value = mock_result

    metrics = await evaluator.evaluate_strategy("strat1")

    assert metrics["brier_score"] == pytest.approx(0.20)
    # Win rate = 0.5
    # Avg confidence = 0.7
    # Overconfidence = 0.7 - 0.5 = 0.2
    assert metrics["overconfidence_index"] == pytest.approx(0.20)

@pytest.mark.asyncio
async def test_fallback_win_loss():
    db = AsyncMock()
    evaluator = OutcomeEvaluator(db)

    # Dec 1: Buy, entry 0.5, exit 0.6 -> Win
    # Dec 2: Sell, entry 0.5, exit 0.6 -> Loss
    dec1 = ShadowDecisionLog(decision="buy", simulated_entry_price=0.5, simulated_exit_price=0.6, confidence=0.8, strategy_id="s")
    dec2 = ShadowDecisionLog(decision="sell", simulated_entry_price=0.5, simulated_exit_price=0.6, confidence=0.2, strategy_id="s")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [dec1, dec2]
    db.execute.return_value = mock_result

    metrics = await evaluator.evaluate_strategy("s")
    assert metrics["win_rate"] == 0.5

@pytest.mark.asyncio
async def test_confidence_bucketing():
    db = AsyncMock()
    evaluator = OutcomeEvaluator(db)

    # Bins: 0.8-0.9 (idx 8), 0.2-0.3 (idx 2)
    dec1 = ShadowDecisionLog(confidence=0.85, actual_ev=10.0, simulated_exit_price=0.6, strategy_id="s1")
    dec2 = ShadowDecisionLog(confidence=0.25, actual_ev=-5.0, simulated_exit_price=0.4, strategy_id="s1")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [dec1, dec2]
    db.execute.return_value = mock_result

    metrics = await evaluator.evaluate_strategy("s1")

    curve = metrics["calibration_curve"]
    assert len(curve) == 2

    # Sort curve by bin or find specific bins
    bin_8 = next(b for b in curve if b["bin"] == "0.8-0.9")
    bin_2 = next(b for b in curve if b["bin"] == "0.2-0.3")

    assert bin_8["count"] == 1
    assert bin_8["actual_win_rate"] == 1.0

    assert bin_2["count"] == 1
    assert bin_2["actual_win_rate"] == 0.0
