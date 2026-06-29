import pytest
from app.services.shadow.report_integrity_validator import ReportIntegrityValidator, ReportIntegrityError
from app.schemas.shadow import PromotionEvidenceSnapshot

def test_report_integrity_validator():
    validator = ReportIntegrityValidator()

    # Valid snapshot
    import uuid
    import hashlib
    import json
    uid = uuid.uuid4()
    decision_ids = [uid]
    source_tables = ["shadow_decision_log"]
    res_range = (None, None)
    recon_data = {
        "decision_ids": [str(uid)],
        "resolution_range": [None, None],
        "source_tables": source_tables
    }
    h = hashlib.sha256(json.dumps(recon_data, sort_keys=True).encode()).hexdigest()

    snapshot = PromotionEvidenceSnapshot(
        strategy_id="s1", decision_count=1, realized_ev=0, replay_parity=1.0,
        brier_score=0.1, certification_violations=0, data_origin="shadow",
        decision_ids=decision_ids, source_tables=source_tables, resolution_range=res_range,
        reconstruction_hash=h
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
    import uuid
    snapshot.data_origin = "shadow"
    snapshot.decision_count = 10
    snapshot.decision_ids = [uuid.uuid4()] # Only 1
    with pytest.raises(ReportIntegrityError, match="Population mismatch"):
        validator.validate_snapshot(snapshot, "NOT_READY")

    # Invalid: Parity sum mismatch
    with pytest.raises(ReportIntegrityError, match="Parity bucket mismatch"):
        validator.validate_parity_report(10, {"EXACT": 5, "UNKNOWN": 4}) # Sum is 9
