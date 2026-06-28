import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from app.services.shadow.parity_service import ParityService
from app.models.shadow_decision_log import ShadowDecisionLog
from app.domain.shadow.models import ReplayParityReport

@pytest.mark.asyncio
async def test_replay_parity_measurement():
    db = AsyncMock()
    service = ParityService(db)

    decision_id = uuid.uuid4()
    log_entry = ShadowDecisionLog(
        id=decision_id,
        replay_match=True,
        confidence=0.8,
        expected_ev=10.0
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = log_entry
    db.execute.return_value = mock_result

    report = await service.measure_parity(decision_id)

    assert report.decision_id == decision_id
    assert report.parity_score == 1.0
    assert report.deterministic is True
    assert report.mismatch_reason is None

@pytest.mark.asyncio
async def test_replay_mismatch_detection():
    db = AsyncMock()
    service = ParityService(db)

    decision_id = uuid.uuid4()
    log_entry = ShadowDecisionLog(
        id=decision_id,
        replay_match=False,
        confidence=0.8,
        expected_ev=10.0
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = log_entry
    db.execute.return_value = mock_result

    report = await service.measure_parity(decision_id)

    assert report.decision_id == decision_id
    assert report.parity_score == 0.0
    assert report.deterministic is False
    assert report.mismatch_reason == "Replay mismatch: fingerprint inconsistency detected"
