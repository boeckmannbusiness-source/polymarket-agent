import pytest
from unittest.mock import AsyncMock
from app.services.shadow.promotion_readiness_service import PromotionReadinessService, ReadinessStatus
from app.schemas.shadow import PromotionEvidenceSnapshot
from datetime import datetime

@pytest.mark.asyncio
async def test_ready_requires_shadow_origin(db_session):
    service = PromotionReadinessService(db_session)

    # Mock a snapshot that passes all thresholds but has synthetic origin
    snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1",
        decision_count=600,
        replay_parity=1.0,
        realized_ev=10.0,
        brier_score=0.1,
        certification_violations=0,
        data_origin="synthetic"
    )

    service.evidence_engine.generate_snapshot = AsyncMock(return_value=snapshot)
    # Force audit to reflect our snapshot
    audit = await service.audit_service.audit_strategy("strat1", snapshot=snapshot)
    assert audit["status"] == "NOT_READY"

    state = await service.get_readiness_state("strat1")
    assert state["readiness_status"] != ReadinessStatus.READY

@pytest.mark.asyncio
async def test_synthetic_origin_rejected(db_session):
    service = PromotionReadinessService(db_session)
    snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1",
        decision_count=600,
        replay_parity=1.0,
        realized_ev=10.0,
        brier_score=0.1,
        certification_violations=0,
        data_origin="synthetic"
    )
    service.evidence_engine.generate_snapshot = AsyncMock(return_value=snapshot)
    state = await service.get_readiness_state("strat1")
    assert state["readiness_status"] != ReadinessStatus.READY

@pytest.mark.asyncio
async def test_mixed_origin_rejected(db_session):
    service = PromotionReadinessService(db_session)
    snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1",
        decision_count=600,
        replay_parity=1.0,
        realized_ev=10.0,
        brier_score=0.1,
        certification_violations=0,
        data_origin="mixed"
    )
    service.evidence_engine.generate_snapshot = AsyncMock(return_value=snapshot)
    state = await service.get_readiness_state("strat1")
    assert state["readiness_status"] != ReadinessStatus.READY

@pytest.mark.asyncio
async def test_status_policy_consistency(db_session):
    service = PromotionReadinessService(db_session)

    # 1. Below threshold
    snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1",
        decision_count=100,
        replay_parity=1.0,
        realized_ev=10.0,
        brier_score=0.1,
        certification_violations=0,
        data_origin="shadow"
    )
    service.evidence_engine.generate_snapshot = AsyncMock(return_value=snapshot)
    state = await service.get_readiness_state("strat1")
    assert state["readiness_status"] == ReadinessStatus.NOT_READY

    # 2. Above threshold + shadow
    snapshot.decision_count = 600
    # Also need to mock audit return value since generate_snapshot was mocked
    service.audit_service.audit_strategy = AsyncMock(return_value={"status": "READY", "reasons": []})

    # We also need some decisions in DB to pass the total_in_db > 0 check
    from app.models.shadow_decision_log import ShadowDecisionLog
    import uuid
    db_session.add(ShadowDecisionLog(id=uuid.uuid4(), strategy_id="strat1"))
    await db_session.commit()

    state = await service.get_readiness_state("strat1")
    assert state["readiness_status"] == ReadinessStatus.READY
