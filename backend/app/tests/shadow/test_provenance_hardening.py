import pytest
import uuid
from datetime import datetime, timezone, timedelta
from app.models.shadow_decision_log import ShadowDecisionLog
from app.services.shadow.evidence_engine import EvidenceEngine
from app.services.shadow.promotion_audit_service import PromotionAuditService
from app.schemas.shadow import PromotionEvidenceSnapshot

@pytest.mark.asyncio
async def test_snapshot_contains_decision_ids(db_session):
    # Create two RESOLVED decisions
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()

    # We also need decisions in DB for data_origin check
    from app.models.shadow_decision_log import ShadowDecisionLog
    # Need > 100 total decisions for many services now, but here we check origin logic
    now = datetime.now(timezone.utc)

    db_session.add(ShadowDecisionLog(
        id=id1, strategy_id="strat1", decision_status="RESOLVED", outcome_timestamp=now,
        simulated_entry_price=1.0, simulated_size=1.0, decision="buy", realized_ev=0.1
    ))
    db_session.add(ShadowDecisionLog(
        id=id2, strategy_id="strat1", decision_status="RESOLVED", outcome_timestamp=now + timedelta(minutes=1),
        simulated_entry_price=1.0, simulated_size=1.0, decision="buy", realized_ev=0.2
    ))
    await db_session.commit()

    engine = EvidenceEngine(db_session)
    snapshot = await engine.generate_snapshot("strat1")

    assert len(snapshot.decision_ids) == 2
    assert id1 in snapshot.decision_ids
    assert id2 in snapshot.decision_ids
    assert snapshot.data_origin == "shadow"
    # Handle possible timezone stripping in SQLite
    res0 = snapshot.resolution_range[0]
    if res0 and res0.tzinfo is None and now.tzinfo is not None:
        res0 = res0.replace(tzinfo=timezone.utc)
    res1 = snapshot.resolution_range[1]
    if res1 and res1.tzinfo is None and now.tzinfo is not None:
        res1 = res1.replace(tzinfo=timezone.utc)

    assert res0 == now
    assert res1 == now + timedelta(minutes=1)

@pytest.mark.asyncio
async def test_mixed_origin_rejected(db_session):
    import uuid
    # Create a synthetic snapshot (manually since EvidenceEngine currently infers)
    snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1",
        decision_count=501,
        replay_parity=1.0,
        realized_ev=0.1,
        brier_score=0.1,
        certification_violations=0,
        data_origin="synthetic",
        decision_ids=[uuid.uuid4()]
    )

    audit_service = PromotionAuditService(db_session)
    audit = await audit_service.audit_strategy("strat1", snapshot=snapshot)

    assert audit["status"] == "NOT_READY"
    assert any("strictly rejected" in r for r in audit["reasons"])
