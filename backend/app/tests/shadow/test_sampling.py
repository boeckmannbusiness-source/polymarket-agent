import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.shadow.sampling_service import ShadowSamplingService
from app.services.shadow.shadow_ledger import ShadowLedger
from app.models.shadow_decision_log import ShadowDecisionLog
from sqlalchemy import select

@pytest.mark.asyncio
async def test_sampling_determinism(db_session: AsyncSession):
    svc = ShadowSamplingService(db_session)
    decision_id = uuid.uuid4()

    res1 = svc.get_sampling_result(decision_id)
    res2 = svc.get_sampling_result(decision_id)

    assert res1 == res2

@pytest.mark.asyncio
async def test_sampling_persistence(db_session: AsyncSession):
    ledger = ShadowLedger(db_session)
    log = await ledger.record_decision(
        market_id="m1",
        signal_id="s1",
        strategy_id="strat1",
        confidence=0.8,
        decision="buy",
        simulated_size=100.0,
        simulated_entry_price=0.5,
        expected_ev=10.0,
        replay_hash="h1",
        replay_match=True,
        certification_version="v1"
    )

    assert log.sampling_bucket is not None
    assert log.sample_reason is not None

    # Verify in DB
    result = await db_session.execute(select(ShadowDecisionLog).where(ShadowDecisionLog.id == log.id))
    db_log = result.scalar_one()
    assert db_log.sampling_bucket == log.sampling_bucket
