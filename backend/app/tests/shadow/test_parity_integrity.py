import pytest
import os
import uuid
from unittest.mock import AsyncMock, MagicMock
from app.services.shadow.dashboard_service import DashboardService
from app.models.shadow_decision_log import ShadowDecisionLog
from app.schemas.shadow import PromotionEvidenceSnapshot
from datetime import datetime

@pytest.mark.asyncio
async def test_replay_bucket_percentages(db_session):
    # Setup: 4 resolved decisions, 2 EXACT, 2 mismatch (UNKNOWN)
    for i in range(2):
        db_session.add(ShadowDecisionLog(id=uuid.uuid4(), decision_status="RESOLVED", replay_match=True))
    for i in range(2):
        db_session.add(ShadowDecisionLog(id=uuid.uuid4(), decision_status="RESOLVED", replay_match=False))
    await db_session.commit()

    dashboard = DashboardService(db_session)
    # Mocking snapshot dependencies for generate_ops_report
    dashboard.evidence_engine.generate_snapshot = AsyncMock(return_value=PromotionEvidenceSnapshot(
        strategy_id="GLOBAL", decision_count=4, realized_ev=0, replay_parity=0.5, brier_score=1.0,
        certification_violations=0, data_origin="shadow"
    ))

    await dashboard.generate_ops_report()

    with open("REPLAY_PARITY_REPORT.md", "r") as f:
        content = f.read()
        assert "EXACT | 2 | 50.00%" in content
        assert "UNKNOWN | 2 | 50.00%" in content
        assert "Reproducibility %**: 50.00%" in content

@pytest.mark.asyncio
async def test_replay_empty_population(db_session):
    dashboard = DashboardService(db_session)
    dashboard.evidence_engine.generate_snapshot = AsyncMock(return_value=PromotionEvidenceSnapshot(
        strategy_id="GLOBAL", decision_count=0, realized_ev=0, replay_parity=0.0, brier_score=1.0,
        certification_violations=0, data_origin="synthetic"
    ))

    await dashboard.generate_ops_report()

    with open("REPLAY_PARITY_REPORT.md", "r") as f:
        content = f.read()
        assert "EXACT | 0 | NOT_AVAILABLE" in content
        assert "Reproducibility %**: NOT_AVAILABLE" in content

@pytest.mark.asyncio
async def test_replay_reproducibility_math(db_session):
    # 10 resolved, 3 EXACT
    for i in range(3):
        db_session.add(ShadowDecisionLog(id=uuid.uuid4(), decision_status="RESOLVED", replay_match=True))
    for i in range(7):
        db_session.add(ShadowDecisionLog(id=uuid.uuid4(), decision_status="RESOLVED", replay_match=False))
    await db_session.commit()

    dashboard = DashboardService(db_session)
    dashboard.evidence_engine.generate_snapshot = AsyncMock(return_value=PromotionEvidenceSnapshot(
        strategy_id="GLOBAL", decision_count=10, realized_ev=0, replay_parity=0.3, brier_score=1.0,
        certification_violations=0, data_origin="shadow"
    ))

    await dashboard.generate_ops_report()

    with open("REPLAY_PARITY_REPORT.md", "r") as f:
        content = f.read()
        assert "EXACT | 3 | 30.00%" in content
        assert "Reproducibility %**: 30.00%" in content
