import pytest
from app.services.shadow.promotion_audit_service import PromotionAuditService
from app.schemas.shadow import PromotionEvidenceSnapshot

@pytest.mark.asyncio
async def test_origin_enforcement(db_session):
    service = PromotionAuditService(db_session)

    # Synthetic origin should never be READY
    snap = PromotionEvidenceSnapshot(
        strategy_id="s1", decision_count=1000, realized_ev=1.0, replay_parity=1.0,
        brier_score=0.1, certification_violations=0, data_origin="synthetic"
    )

    audit = await service.audit_strategy("s1", snapshot=snap)
    assert audit["status"] == "NOT_READY"
    assert any("strictly rejected" in r for r in audit["reasons"])
