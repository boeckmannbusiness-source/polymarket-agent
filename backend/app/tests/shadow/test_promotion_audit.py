import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.shadow.promotion_audit_service import PromotionAuditService
from app.schemas.shadow import PromotionEvidenceSnapshot
from datetime import datetime

@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_policy_threshold_enforcement(mock_db):
    service = PromotionAuditService(mock_db)

    # Mock ready snapshot
    now = datetime.now()
    ready_snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1",
        decision_count=600,
        replay_parity=0.98,
        realized_ev=10.0,
        brier_score=0.15,
        certification_violations=0,
        timestamp=now,
        snapshot_hash="ready_hash"
    )

    service.evidence_engine.generate_snapshot = AsyncMock(return_value=ready_snapshot)

    audit = await service.audit_strategy("strat1")
    assert audit["status"] == "READY"
    assert len(audit["reasons"]) == 0

@pytest.mark.asyncio
async def test_not_ready_reason_generation(mock_db):
    service = PromotionAuditService(mock_db)

    # Mock failing snapshot
    now = datetime.now()
    failing_snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1",
        decision_count=100, # Too low
        replay_parity=0.90, # Too low
        realized_ev=-5.0,   # Negative
        brier_score=0.40,    # Too high
        certification_violations=1, # Violation
        timestamp=now,
        snapshot_hash="fail_hash"
    )

    service.evidence_engine.generate_snapshot = AsyncMock(return_value=failing_snapshot)

    audit = await service.audit_strategy("strat1")
    assert audit["status"] == "NOT_READY"
    assert len(audit["reasons"]) == 5
    assert any("Insufficient decision volume" in r for r in audit["reasons"])
    assert any("Replay parity below threshold" in r for r in audit["reasons"])
    assert any("Positive realized EV required" in r for r in audit["reasons"])
    assert any("Confidence calibration unstable" in r for r in audit["reasons"])
    assert any("Certification violations detected" in r for r in audit["reasons"])

@pytest.mark.asyncio
async def test_policy_reload(mock_db):
    service = PromotionAuditService(mock_db)

    with patch("app.services.shadow.promotion_audit_service.parse_promotion_policy") as mock_parse:
        mock_parse.return_value = {"min_decisions": 1000}

        now = datetime.now()
        snapshot = PromotionEvidenceSnapshot(
            strategy_id="s1", decision_count=600, replay_parity=0.98, realized_ev=10.0,
            brier_score=0.1, certification_violations=0, timestamp=now, snapshot_hash="h"
        )
        service.evidence_engine.generate_snapshot = AsyncMock(return_value=snapshot)

        audit = await service.audit_strategy("strat1")
        assert audit["status"] == "NOT_READY"
        assert any("1000" in r for r in audit["reasons"])

        mock_parse.assert_called_once()
