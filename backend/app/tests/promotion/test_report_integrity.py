import pytest
from app.services.shadow.report_integrity_validator import ReportIntegrityValidator, ReportIntegrityError
from app.schemas.shadow import PromotionEvidenceSnapshot

def test_report_integrity():
    validator = ReportIntegrityValidator()
    # READY + synthetic should fail
    snap = PromotionEvidenceSnapshot(
        strategy_id="s1", decision_count=0, realized_ev=0, replay_parity=1.0,
        brier_score=0.1, certification_violations=0, data_origin="synthetic"
    )
    with pytest.raises(ReportIntegrityError, match="Status READY is incompatible with origin 'synthetic'"):
        validator.validate_snapshot(snap, "READY")
