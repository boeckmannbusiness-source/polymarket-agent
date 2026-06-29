import pytest
import uuid
from datetime import datetime, timezone, timedelta
from app.models.shadow_decision_log import ShadowDecisionLog
from app.services.shadow.promotion_readiness_service import PromotionReadinessService

@pytest.mark.asyncio
async def test_forecast_requires_real_volume(db_session):
    service = PromotionReadinessService(db_session)

    # Case 1: No volume
    state = await service.get_readiness_state("strat1")
    assert state["forecast"]["estimated_days_to_500"] == "UNKNOWN"

    # Case 2: Some volume in last 7 days
    now = datetime.now(timezone.utc)
    for i in range(14): # 2 per day
        db_session.add(ShadowDecisionLog(
            id=uuid.uuid4(), strategy_id="strat1", decision_status="RESOLVED",
            outcome_timestamp=now - timedelta(days=i/2),
            simulated_entry_price=1.0, simulated_size=1.0, decision="buy", realized_ev=0.1
        ))
    await db_session.commit()

    state = await service.get_readiness_state("strat1")
    # 14 decisions in 7 days = 2.0 per day
    # current decision_count = 14
    # remaining = 500 - 14 = 486
    # eta = 486 / 2.0 = 243.0

    assert state["forecast"]["rolling_7d"] == 2.0
    assert state["forecast"]["estimated_days_to_500"] == 243.0
