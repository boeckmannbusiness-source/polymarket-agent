import pytest
from unittest.mock import AsyncMock
from app.services.shadow.promotion_readiness_service import PromotionReadinessService
from app.schemas.shadow import PromotionEvidenceSnapshot

@pytest.mark.asyncio
async def test_forecast_unknown_eta(db_session):
    service = PromotionReadinessService(db_session)
    # Zero throughput
    snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1", decision_count=0, realized_ev=0, replay_parity=0,
        brier_score=1.0, certification_violations=0, data_origin="synthetic"
    )
    service.evidence_engine.generate_snapshot = AsyncMock(return_value=snapshot)

    state = await service.get_readiness_state("strat1")
    assert state["forecast"]["estimated_days_to_500"] == "UNKNOWN"

@pytest.mark.asyncio
async def test_no_dash_placeholders(db_session):
    service = PromotionReadinessService(db_session)
    snapshot = PromotionEvidenceSnapshot(
        strategy_id="strat1", decision_count=0, realized_ev=0, replay_parity=0,
        brier_score=1.0, certification_violations=0, data_origin="synthetic"
    )
    service.evidence_engine.generate_snapshot = AsyncMock(return_value=snapshot)

    state = await service.get_readiness_state("strat1")
    # All values should be UNKNOWN or NOT_AVAILABLE or numbers, but NOT "-"
    for key, val in state["forecast"].items():
        assert val != "-"
        if val is None:
            # Our sanitizer should have caught this
            pytest.fail(f"Key {key} has None value")
