import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.shadow_decision_log import ShadowDecisionLog
from app.services.shadow.stability_engine import ShadowStabilityEngine
import uuid

@pytest.mark.asyncio
async def test_stability_windows(db_session: AsyncSession):
    strategy_id = "strat_stable"
    now = datetime.now(timezone.utc)

    # Create some resolved decisions in various windows
    # 7d window
    for i in range(5):
        d = ShadowDecisionLog(
            id=uuid.uuid4(),
            strategy_id=strategy_id,
            decision_status="RESOLVED",
            outcome_timestamp=now - timedelta(days=2),
            realized_ev=10.0,
            actual_ev=10.0,
            expected_ev=8.0,
            replay_match=True
        )
        db_session.add(d)

    await db_session.commit()

    svc = ShadowStabilityEngine(db_session)
    metrics_7d = await svc.compute_window_metrics(strategy_id, 7)

    assert metrics_7d["status"] == "OK"
    assert metrics_7d["decision_count"] == 5
    assert metrics_7d["realized_ev_avg"] == 10.0
    assert metrics_7d["replay_stability"] == 1.0

@pytest.mark.asyncio
async def test_stability_not_available(db_session: AsyncSession):
    svc = ShadowStabilityEngine(db_session)
    metrics = await svc.compute_window_metrics("non_existent", 7)
    assert metrics["status"] == "NOT_AVAILABLE"
