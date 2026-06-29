import pytest
import uuid
import hashlib
import json
from app.schemas.shadow import PromotionEvidenceSnapshot

def test_snapshot_reconstruction():
    decision_ids = [uuid.uuid4(), uuid.uuid4()]
    source_tables = ["shadow_decision_log"]
    res_range = (None, None)

    recon_data = {
        "decision_ids": [str(uid) for uid in decision_ids],
        "resolution_range": [ts.isoformat() if ts else None for ts in res_range],
        "source_tables": source_tables
    }
    expected_hash = hashlib.sha256(json.dumps(recon_data, sort_keys=True).encode()).hexdigest()

    snap = PromotionEvidenceSnapshot(
        strategy_id="s1", decision_count=2, realized_ev=0, replay_parity=1.0,
        brier_score=0.1, certification_violations=0, data_origin="shadow",
        decision_ids=decision_ids, source_tables=source_tables, resolution_range=res_range,
        reconstruction_hash=expected_hash
    )

    assert snap.reconstruction_hash == expected_hash
