import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.shadow_decision_log import ShadowDecisionLog
from app.services.shadow.outcome_engine import OutcomeClosureEngine

@pytest.mark.asyncio
async def test_open_to_closed_to_resolved_transition(db_session):
    # Create an OPEN decision
    decision_id = uuid.uuid4()
    log_entry = ShadowDecisionLog(
        id=decision_id,
        decision_status="OPEN",
        simulated_entry_price=100.0,
        simulated_size=1.0,
        decision="buy"
    )
    db_session.add(log_entry)
    await db_session.commit()

    engine = OutcomeClosureEngine(db_session)
    await engine.resolve_decision(decision_id, resolution_price=110.0)

    # Verify final state
    result = await db_session.execute(
        select(ShadowDecisionLog).where(ShadowDecisionLog.id == decision_id)
    )
    updated_entry = result.scalar_one()
    assert updated_entry.decision_status == "RESOLVED"
    assert updated_entry.realized_ev == 10.0

@pytest.mark.asyncio
async def test_invalid_transition_rejected(db_session):
    # Create a RESOLVED decision
    decision_id = uuid.uuid4()
    log_entry = ShadowDecisionLog(
        id=decision_id,
        decision_status="RESOLVED",
        simulated_entry_price=100.0,
        simulated_size=1.0,
        decision="buy"
    )
    db_session.add(log_entry)
    await db_session.commit()

    engine = OutcomeClosureEngine(db_session)

    # Attempting to resolve a RESOLVED decision should fail
    with pytest.raises(ValueError, match="Invalid transition"):
        await engine.resolve_decision(decision_id, resolution_price=110.0)
