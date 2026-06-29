import pytest
import uuid
from app.models.shadow_decision_log import ShadowDecisionLog
from app.services.shadow.parity_service import ParityService

@pytest.mark.asyncio
async def test_parity_classification(db_session):
    # Case 1: EXACT
    id1 = uuid.uuid4()
    db_session.add(ShadowDecisionLog(
        id=id1, replay_match=True, confidence=0.8, expected_ev=0.1
    ))

    # Case 2: UNKNOWN mismatch
    id2 = uuid.uuid4()
    db_session.add(ShadowDecisionLog(
        id=id2, replay_match=False, confidence=0.8, expected_ev=0.1
    ))
    await db_session.commit()

    parity_service = ParityService(db_session)

    report1 = await parity_service.measure_parity(id1)
    assert report1.category == "EXACT"
    assert report1.parity_score == 1.0

    report2 = await parity_service.measure_parity(id2)
    assert report2.category == "UNKNOWN"
    assert report2.parity_score == 0.0
