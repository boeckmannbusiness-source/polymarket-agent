import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.shadow.explanation_service import ExplanationService
from app.models.decision_explanation import DecisionExplanation

@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_decision_explanation(mock_db):
    service = ExplanationService(mock_db)
    decision_id = uuid.uuid4()

    # Test storing
    inputs = {"market_trend": "bullish", "volume_24h": 1000000}
    await service.store_explanation(
        decision_id=decision_id,
        strategy_inputs=inputs,
        expected_outcome="positive",
        confidence_reasoning="Strong trend and volume alignment"
    )

    assert mock_db.add.called
    explanation = mock_db.add.call_args[0][0]
    assert explanation.decision_id == decision_id
    assert explanation.strategy_inputs == inputs

@pytest.mark.asyncio
async def test_explanation_determinism(mock_db):
    service = ExplanationService(mock_db)
    decision_id = uuid.uuid4()

    # Mock retrieval
    stored_explanation = DecisionExplanation(
        decision_id=decision_id,
        strategy_inputs={"a": 1},
        expected_outcome="win",
        replay_reference="hash123"
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = stored_explanation
    mock_db.execute.return_value = mock_res

    retrieved = await service.get_explanation(decision_id)
    assert retrieved is not None
    assert retrieved.replay_reference == "hash123"
    assert retrieved.strategy_inputs == {"a": 1}
