import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.shadow.dashboard_service import DashboardService
from app.schemas.shadow import ScorecardMetrics, PromotionEvidenceSnapshot
from datetime import datetime

@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_dashboard_generation(mock_db):
    service = DashboardService(mock_db)

    # Mock snapshots
    now = datetime.now()
    global_snap = PromotionEvidenceSnapshot(
        strategy_id="GLOBAL", decision_count=100, realized_ev=50.0,
        replay_parity=0.98, brier_score=0.1, certification_violations=0,
        data_origin="shadow", decision_ids=["id"] * 100,
        timestamp=now, snapshot_hash="global_hash"
    )
    strat_snap = PromotionEvidenceSnapshot(
        strategy_id="strat1", decision_count=100, realized_ev=50.0,
        replay_parity=0.98, brier_score=0.1, certification_violations=0,
        data_origin="shadow", decision_ids=["id"] * 100,
        timestamp=now, snapshot_hash="strat_hash"
    )
    service.evidence_engine.generate_snapshot = AsyncMock(side_effect=[global_snap, strat_snap])

    # Mock strategy list
    mock_strat_res = MagicMock()
    mock_strat_res.scalars.return_value.all.return_value = ["strat1"]
    mock_db.execute.return_value = mock_strat_res

    # Mock audit and stability
    service.audit_service.audit_strategy = AsyncMock(return_value={
        "status": "READY",
        "metrics": strat_snap.model_dump(),
        "timestamp": now.isoformat(),
        "snapshot_hash": "strat_hash",
        "thresholds": {},
        "reasons": []
    })
    service.stability_monitor.check_stability = AsyncMock(return_value=[])

    report = await service.generate_ops_report()

    assert "# SHADOW_OPERATIONS_REPORT" in report
    assert "strat1" in report
    assert "READY" in report
    assert os.path.exists("SHADOW_OPERATIONS_REPORT.md")
    assert os.path.exists("PROMOTION_EVIDENCE_REPORT.md")

@pytest.mark.asyncio
async def test_dashboard_consistency(mock_db):
    service = DashboardService(mock_db)

    # Verify that it handles empty strategies
    mock_strat_res = MagicMock()
    mock_strat_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_strat_res

    now = datetime.now()
    global_snap = PromotionEvidenceSnapshot(
        strategy_id="GLOBAL", decision_count=0, realized_ev=0.0,
        replay_parity=0.0, brier_score=1.0, certification_violations=0,
        timestamp=now, snapshot_hash="empty_hash"
    )
    service.evidence_engine.generate_snapshot = AsyncMock(return_value=global_snap)

    report = await service.generate_ops_report()
    # Updated text to match SHADOW_OPERATIONS_REPORT
    assert "Total Resolved Decisions | 0" in report
