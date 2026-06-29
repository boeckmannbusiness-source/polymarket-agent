import pytest
import uuid
from app.services.shadow.evidence_replay_auditor import PromotionReplayAuditor, EvidenceReplayMismatch
from app.schemas.shadow import PromotionEvidenceSnapshot
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_evidence_replay_audit_pass(db_session):
    auditor = PromotionReplayAuditor(db_session)

    # Mock snapshot
    snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1",
        decision_count=10,
        realized_ev=5.0,
        replay_parity=1.0,
        brier_score=0.1,
        certification_violations=0,
        decision_ids=[uuid.uuid4() for _ in range(10)]
    )

    # Mock scorecard engine to return matching metrics
    mock_scorecard = MagicMock()
    mock_scorecard.global_metrics.decision_count = 10
    mock_scorecard.global_metrics.realized_ev = 5.0
    mock_scorecard.global_metrics.replay_parity = 1.0
    mock_scorecard.global_metrics.brier_score = 0.1

    auditor.scorecard_engine.generate_scorecard = AsyncMock(return_value=mock_scorecard)

    assert await auditor.audit_snapshot(snapshot) is True

@pytest.mark.asyncio
async def test_evidence_replay_audit_mismatch(db_session):
    auditor = PromotionReplayAuditor(db_session)

    snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1",
        decision_count=10,
        realized_ev=5.0,
        replay_parity=1.0,
        brier_score=0.1,
        certification_violations=0,
        decision_ids=[uuid.uuid4() for _ in range(10)]
    )

    # Recomputed realized_ev is different
    mock_scorecard = MagicMock()
    mock_scorecard.global_metrics.decision_count = 10
    mock_scorecard.global_metrics.realized_ev = 4.0 # Mismatch
    mock_scorecard.global_metrics.replay_parity = 1.0
    mock_scorecard.global_metrics.brier_score = 0.1

    auditor.scorecard_engine.generate_scorecard = AsyncMock(return_value=mock_scorecard)

    with pytest.raises(EvidenceReplayMismatch, match="Metric mismatch in realized_ev"):
        await auditor.audit_snapshot(snapshot)
