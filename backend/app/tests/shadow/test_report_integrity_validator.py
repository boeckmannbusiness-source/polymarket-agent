import pytest
from app.services.shadow.report_integrity_validator import ReportIntegrityValidator, ReportIntegrityError
from app.schemas.shadow import PromotionEvidenceSnapshot

def test_report_integrity_validator():
    validator = ReportIntegrityValidator()

    # Valid snapshot
    snapshot = PromotionEvidenceSnapshot(
        strategy_id="s1", decision_count=1, realized_ev=0, replay_parity=1.0,
        brier_score=0.1, certification_violations=0, data_origin="shadow",
        decision_ids=["id1"]
    )
    assert validator.validate_snapshot(snapshot, "READY") is True

    # Valid parity
    assert validator.validate_parity_report(10, {"EXACT": 8, "UNKNOWN": 2}) is True

def test_invalid_report_rejected():
    validator = ReportIntegrityValidator()

    # Invalid: READY + synthetic
    snapshot = PromotionEvidenceSnapshot(
        strategy_id="s1", decision_count=0, realized_ev=0, replay_parity=1.0,
        brier_score=0.1, certification_violations=0, data_origin="synthetic"
    )
    with pytest.raises(ReportIntegrityError, match="Status READY is incompatible"):
        validator.validate_snapshot(snapshot, "READY")

    # Invalid: Population mismatch
    snapshot.data_origin = "shadow"
    snapshot.decision_count = 10
    snapshot.decision_ids = ["id1"] # Only 1
    with pytest.raises(ReportIntegrityError, match="Population mismatch"):
        validator.validate_snapshot(snapshot, "NOT_READY")

    # Invalid: Parity sum mismatch
    with pytest.raises(ReportIntegrityError, match="Parity bucket mismatch"):
        validator.validate_parity_report(10, {"EXACT": 5, "UNKNOWN": 4}) # Sum is 9
