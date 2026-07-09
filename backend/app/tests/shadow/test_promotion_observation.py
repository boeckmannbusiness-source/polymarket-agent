import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.shadow_decision_log import ShadowDecisionLog
from app.services.shadow.promotion_observation_service import PromotionObservationService
import uuid
from datetime import datetime, timezone, timedelta

@pytest.mark.asyncio
async def test_promotion_lifecycle_states(db_session: AsyncSession):
    strategy_id = "strat_obs"
    svc = PromotionObservationService(db_session)

    # State 1: COLLECTING
    res = await svc.evaluate_readiness(strategy_id)
    assert res["state"] == "COLLECTING"

    # State 2: OBSERVING (add > 100 resolved)
    for i in range(101):
        d = ShadowDecisionLog(
            id=uuid.uuid4(),
            strategy_id=strategy_id,
            decision_status="RESOLVED",
            outcome_timestamp=datetime.now(timezone.utc),
            realized_ev=1.0,
            replay_match=True
        )
        db_session.add(d)
    await db_session.commit()

    res = await svc.evaluate_readiness(strategy_id)
    assert res["state"] == "OBSERVING"

    # State 3: READY_CANDIDATE (add > 500 resolved and stable)
    for i in range(400):
        d = ShadowDecisionLog(
            id=uuid.uuid4(),
            strategy_id=strategy_id,
            decision_status="RESOLVED",
            outcome_timestamp=datetime.now(timezone.utc),
            realized_ev=1.0,
            replay_match=True
        )
        db_session.add(d)
    await db_session.commit()

    res = await svc.evaluate_readiness(strategy_id)
    assert res["state"] == "READY_CANDIDATE"
