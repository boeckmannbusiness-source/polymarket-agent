import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.shadow_decision_log import ShadowDecisionLog
from app.services.shadow.aging_service import ShadowAgingService
from sqlalchemy import select

@pytest.mark.asyncio
async def test_aging_transitions(db_session: AsyncSession):
    # Create an old OPEN decision
    old_date = datetime.now(timezone.utc) - timedelta(hours=30)
    log = ShadowDecisionLog(
        id=uuid_gen(),
        timestamp=old_date,
        decision_status="OPEN",
        strategy_id="strat1"
    )
    db_session.add(log)

    # Create a fresh OPEN decision
    fresh_log = ShadowDecisionLog(
        id=uuid_gen(),
        timestamp=datetime.now(timezone.utc),
        decision_status="OPEN",
        strategy_id="strat1"
    )
    db_session.add(fresh_log)

    await db_session.commit()

    svc = ShadowAgingService(db_session)
    stale_count = await svc.check_aging()

    assert stale_count == 1

    # Refresh from DB
    res = await db_session.execute(select(ShadowDecisionLog).where(ShadowDecisionLog.id == log.id))
    assert res.scalar_one().decision_status == "STALE"

    res_fresh = await db_session.execute(select(ShadowDecisionLog).where(ShadowDecisionLog.id == fresh_log.id))
    assert res_fresh.scalar_one().decision_status == "OPEN"

def uuid_gen():
    import uuid
    return uuid.uuid4()
