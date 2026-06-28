import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.services.shadow.outcome_engine import OutcomeClosureEngine
from app.models.shadow_decision_log import ShadowDecisionLog
from app.domain.shadow.models import OutcomeReceipt

@pytest.mark.asyncio
async def test_outcome_resolution():
    db = AsyncMock()
    engine = OutcomeClosureEngine(db)

    decision_id = uuid.uuid4()
    log_entry = ShadowDecisionLog(
        id=decision_id,
        simulated_entry_price=0.5,
        simulated_size=100.0,
        decision="buy",
        confidence=0.8,
        predicted_probability=0.75
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = log_entry
    db.execute.return_value = mock_result

    resolution_price = 0.6
    receipt = await engine.resolve_decision(decision_id, resolution_price)

    assert receipt.decision_id == decision_id
    assert receipt.resolution_price == 0.6
    # buy: (0.6 - 0.5) * 100 = 10.0
    assert receipt.realized_ev == pytest.approx(10.0)
    assert receipt.win_loss is True
    # outcome_val = 1.0 (win)
    # prediction_error = |0.8 - 1.0| = 0.2
    assert receipt.prediction_error == pytest.approx(0.2)
    # calibration_delta = 0.75 - 1.0 = -0.25
    assert receipt.calibration_delta == pytest.approx(-0.25)

@pytest.mark.asyncio
async def test_ev_calculation():
    db = AsyncMock()
    engine = OutcomeClosureEngine(db)

    decision_id = uuid.uuid4()
    # Sell case
    log_entry = ShadowDecisionLog(
        id=decision_id,
        simulated_entry_price=0.5,
        simulated_size=100.0,
        decision="sell",
        confidence=0.4,
        predicted_probability=0.45
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = log_entry
    db.execute.return_value = mock_result

    resolution_price = 0.6
    receipt = await engine.resolve_decision(decision_id, resolution_price)

    # sell: (0.6 - 0.5) = 0.1, -0.1 * 100 = -10.0
    assert receipt.realized_ev == pytest.approx(-10.0)
    assert receipt.win_loss is False
    # outcome_val = 0.0 (loss)
    # prediction_error = |0.4 - 0.0| = 0.4
    assert receipt.prediction_error == pytest.approx(0.4)
    # calibration_delta = 0.45 - 0.0 = 0.45
    assert receipt.calibration_delta == pytest.approx(0.45)

def test_outcome_receipt_immutable():
    receipt = OutcomeReceipt(
        decision_id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        realized_ev=10.0,
        win_loss=True,
        calibration_delta=0.1,
        prediction_error=0.2,
        resolution_price=0.6
    )

    with pytest.raises(Exception): # Pydantic v2 raises ValidationError or AttributeError depending on access
        receipt.realized_ev = 20.0
