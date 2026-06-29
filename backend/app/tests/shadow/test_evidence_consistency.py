import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.shadow.evidence_engine import EvidenceEngine
from app.services.shadow.dashboard_service import DashboardService
from app.services.shadow.promotion_audit_service import PromotionAuditService
from app.schemas.shadow import ScorecardMetrics, StrategyScorecard, PromotionEvidenceSnapshot
from datetime import datetime

@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_reports_use_same_snapshot(mock_db):
    evidence_engine = EvidenceEngine(mock_db)
    audit_service = PromotionAuditService(mock_db)

    # Generate one snapshot
    metrics = ScorecardMetrics(decision_count=100, realized_ev=50.0)
    scorecard = StrategyScorecard(
        strategy_id="s1", global_metrics=metrics, rolling_7d=metrics, rolling_30d=metrics
    )
    evidence_engine.scorecard_engine.generate_scorecard = AsyncMock(return_value=scorecard)

    mock_res = MagicMock()
    mock_res.scalar.return_value = 0
    mock_db.execute.return_value = mock_res

    snapshot = await evidence_engine.generate_snapshot("s1")

    # Audit using this snapshot
    audit = await audit_service.audit_strategy("s1", snapshot=snapshot)

    assert audit["snapshot_hash"] == snapshot.snapshot_hash
    assert audit["metrics"]["decision_count"] == snapshot.decision_count

@pytest.mark.asyncio
async def test_snapshot_consistency(mock_db):
    evidence_engine = EvidenceEngine(mock_db)

    metrics = ScorecardMetrics(decision_count=500, replay_parity=0.96)
    scorecard = StrategyScorecard(
        strategy_id="s1", global_metrics=metrics, rolling_7d=metrics, rolling_30d=metrics
    )
    evidence_engine.scorecard_engine.generate_scorecard = AsyncMock(return_value=scorecard)

    mock_res = MagicMock()
    mock_res.scalar.return_value = 0
    mock_db.execute.return_value = mock_res

    snapshot1 = await evidence_engine.generate_snapshot("s1")
    snapshot2 = await evidence_engine.generate_snapshot("s1")

    # Hashes should match if data is same (ignoring timestamp in hash calculation)
    assert snapshot1.snapshot_hash == snapshot2.snapshot_hash

@pytest.mark.asyncio
async def test_strategy_vs_global_consistency(mock_db):
    dashboard = DashboardService(mock_db)

    # Mocking global and strategy snapshots to return specific values
    dashboard.evidence_engine.generate_snapshot = AsyncMock()

    now = datetime.now()
    import uuid
    import hashlib
    import json
    uids_global = [uuid.uuid4() for _ in range(1000)]
    recon_data_global = {
        "decision_ids": [str(uid) for uid in uids_global],
        "resolution_range": [None, None],
        "source_tables": ["shadow_decision_log"]
    }
    h_global = hashlib.sha256(json.dumps(recon_data_global, sort_keys=True).encode()).hexdigest()

    uids_strat = [uuid.uuid4() for _ in range(500)]
    recon_data_strat = {
        "decision_ids": [str(uid) for uid in uids_strat],
        "resolution_range": [None, None],
        "source_tables": ["shadow_decision_log"]
    }
    h_strat = hashlib.sha256(json.dumps(recon_data_strat, sort_keys=True).encode()).hexdigest()

    global_snap = PromotionEvidenceSnapshot(
        strategy_id="GLOBAL", decision_count=1000, realized_ev=100.0,
        replay_parity=0.98, brier_score=0.1, certification_violations=0,
        data_origin="shadow", decision_ids=uids_global,
        timestamp=now, snapshot_hash="global_hash", reconstruction_hash=h_global
    )
    strat_snap = PromotionEvidenceSnapshot(
        strategy_id="strat1", decision_count=500, realized_ev=50.0,
        replay_parity=0.97, brier_score=0.15, certification_violations=0,
        data_origin="shadow", decision_ids=uids_strat,
        timestamp=now, snapshot_hash="strat_hash", reconstruction_hash=h_strat
    )

    dashboard.evidence_engine.generate_snapshot.side_effect = [global_snap, strat_snap, strat_snap]

    mock_strat_res = MagicMock()
    mock_strat_res.scalars.return_value.all.return_value = ["strat1"]
    mock_db.execute.return_value = mock_strat_res

    # Mock audit and stability
    dashboard.audit_service.audit_strategy = AsyncMock(return_value={
        "status": "READY",
        "metrics": strat_snap.model_dump(),
        "timestamp": now.isoformat(),
        "snapshot_hash": "strat_hash",
        "reasons": [],
        "thresholds": {"min_decisions": 500, "min_replay_parity": 0.95, "max_brier_score": 0.25}
    })
    dashboard.stability_monitor.check_stability = AsyncMock(return_value=[])

    report = await dashboard.generate_ops_report()

    assert "Global Snapshot Hash: global_hash" in report
    assert "strat_hash" in report
