import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.shadow.readiness_evaluator import PromotionReadinessEvaluator
from app.services.shadow.promotion_audit_service import PromotionAuditService
from app.schemas.shadow import PromotionEvidenceSnapshot
from datetime import datetime

@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_ready_requires_all_rules(mock_db):
    evaluator = PromotionReadinessEvaluator(mock_db)

    # Mock ready metrics
    evaluator.evaluator.evaluate_strategy = AsyncMock(return_value={
        "total_decisions": 600,
        "realized_ev": 10.0,
        "brier_score": 0.15
    })
    evaluator.evaluator.get_global_metrics = AsyncMock(return_value={
        "replay_parity": 0.98,
        "certification_violations": 0
    })

    result = await evaluator.evaluate_readiness("s1")
    assert result["status"] == "READY"
    assert len(result["blocking_reasons"]) == 0

@pytest.mark.asyncio
async def test_failed_metric_blocks_promotion(mock_db):
    evaluator = PromotionReadinessEvaluator(mock_db)

    # One failing metric: decision volume
    evaluator.evaluator.evaluate_strategy = AsyncMock(return_value={
        "total_decisions": 100,
        "realized_ev": 10.0,
        "brier_score": 0.15
    })
    evaluator.evaluator.get_global_metrics = AsyncMock(return_value={
        "replay_parity": 0.98,
        "certification_violations": 0
    })

    result = await evaluator.evaluate_readiness("s1")
    assert result["status"] == "NOT_READY"
    assert any("Insufficient decision volume" in r for r in result["blocking_reasons"])

@pytest.mark.asyncio
async def test_blocking_reasons_generated(mock_db):
    service = PromotionAuditService(mock_db)

    now = datetime.now()
    failing_snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1",
        decision_count=100,
        replay_parity=0.90,
        realized_ev=-5.0,
        brier_score=0.40,
        certification_violations=0,
        timestamp=now,
        snapshot_hash="fail"
    )

    service.evidence_engine.generate_snapshot = AsyncMock(return_value=failing_snapshot)

    audit = await service.audit_strategy("strat1")
    assert audit["status"] == "NOT_READY"
    assert len(audit["reasons"]) == 4
