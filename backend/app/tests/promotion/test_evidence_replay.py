import pytest
from app.services.shadow.evidence_replay_auditor import PromotionReplayAuditor, EvidenceReplayMismatch
from app.schemas.shadow import PromotionEvidenceSnapshot
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_evidence_replay(db_session):
    import uuid
    auditor = PromotionReplayAuditor(db_session)
    snap = PromotionEvidenceSnapshot(
        strategy_id="s1", decision_count=1, realized_ev=1.0, replay_parity=1.0,
        brier_score=0.1, certification_violations=0, data_origin="shadow",
        decision_ids=[uuid.uuid4()]
    )

    mock_scorecard = MagicMock()
    mock_scorecard.global_metrics.decision_count = 1
    mock_scorecard.global_metrics.realized_ev = 1.0
    mock_scorecard.global_metrics.replay_parity = 1.0
    mock_scorecard.global_metrics.brier_score = 0.1
    auditor.scorecard_engine.generate_scorecard = AsyncMock(return_value=mock_scorecard)

    assert await auditor.audit_snapshot(snap) is True

    # Mismatch
    snap.realized_ev = 2.0
    with pytest.raises(EvidenceReplayMismatch):
        await auditor.audit_snapshot(snap)
