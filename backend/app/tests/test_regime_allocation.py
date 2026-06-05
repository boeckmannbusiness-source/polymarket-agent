import pytest
from app.services.intelligence.regime_allocation_service import RegimeAllocationService


@pytest.fixture
def service():
    svc = RegimeAllocationService()
    svc._local_plans.clear()
    return svc


@pytest.mark.asyncio
async def test_generate_returns_plan(service):
    plan = await service.generate("trending", 0.8, [])
    assert plan is not None
    assert plan.regime == "trending"
    assert plan.regime_confidence == 0.8
    assert plan.generated_at != ""


@pytest.mark.asyncio
async def test_trending_increases_momentum(service):
    allocs = [{"strategy_id": "mom1", "allocation": 20}, {"strategy_id": "rev1", "allocation": 20}]
    archs = {"mom1": "momentum_trend", "rev1": "mean_reversion"}
    plan = await service.generate("trending", 0.8, allocs, strategy_archetypes=archs)
    mom_adj = [a for a in plan.adjustments if a.strategy_id == "mom1"]
    rev_adj = [a for a in plan.adjustments if a.strategy_id == "rev1"]
    assert any(a.delta > 0 for a in mom_adj)
    assert any(a.delta < 0 for a in rev_adj)


@pytest.mark.asyncio
async def test_mean_reverting_increases_contrarian(service):
    allocs = [{"strategy_id": "rev1", "allocation": 20}, {"strategy_id": "mom1", "allocation": 20}]
    archs = {"rev1": "mean_reversion", "mom1": "momentum_trend"}
    plan = await service.generate("mean_reverting", 0.7, allocs, strategy_archetypes=archs)
    rev_adj = [a for a in plan.adjustments if a.strategy_id == "rev1"]
    mom_adj = [a for a in plan.adjustments if a.strategy_id == "mom1"]
    assert any(a.delta > 0 for a in rev_adj)
    assert any(a.delta < 0 for a in mom_adj)


@pytest.mark.asyncio
async def test_high_volatility_reduces_concentration(service):
    allocs = [{"strategy_id": "gen1", "allocation": 50}]
    archs = {"gen1": "generic"}
    plan = await service.generate("high_volatility", 0.6, allocs, strategy_archetypes=archs)
    for a in plan.adjustments:
        assert a.delta <= 0


@pytest.mark.asyncio
async def test_news_driven_favors_sentiment(service):
    allocs = [{"strategy_id": "nlp1", "allocation": 20}, {"strategy_id": "gen1", "allocation": 20}]
    archs = {"nlp1": "ml_sentiment", "gen1": "generic"}
    plan = await service.generate("news_driven", 0.9, allocs, strategy_archetypes=archs)
    nlp_adj = [a for a in plan.adjustments if a.strategy_id == "nlp1"]
    assert any(a.delta > 0 for a in nlp_adj)


@pytest.mark.asyncio
async def test_tier_caps_respected(service):
    allocs = [{"strategy_id": "mom1", "allocation": 20}]
    archs = {"mom1": "momentum_trend"}
    caps = {"mom1": 22}
    plan = await service.generate("trending", 0.9, allocs, tier_caps=caps, strategy_archetypes=archs)
    for a in plan.adjustments:
        assert a.to_allocation <= 22


@pytest.mark.asyncio
async def test_get_latest(service):
    await service.generate("trending", 0.8, [])
    latest = await service.get_latest()
    assert latest is not None
    assert latest.regime == "trending"


@pytest.mark.asyncio
async def test_get_all(service):
    await service.generate("trending", 0.8, [])
    await service.generate("mean_reverting", 0.6, [])
    plans = await service.get_all()
    assert len(plans) >= 2


@pytest.mark.asyncio
async def test_deterministic(service):
    allocs = [{"strategy_id": "mom1", "allocation": 20}]
    archs = {"mom1": "momentum_trend"}
    p1 = await service.generate("trending", 0.8, allocs, strategy_archetypes=archs)
    svc2 = RegimeAllocationService()
    svc2._local_plans.clear()
    p2 = await svc2.generate("trending", 0.8, allocs, strategy_archetypes=archs)
    assert len(p1.adjustments) == len(p2.adjustments)


@pytest.mark.asyncio
async def test_explainable_rationale(service):
    allocs = [{"strategy_id": "mom1", "allocation": 20}]
    archs = {"mom1": "momentum_trend"}
    plan = await service.generate("trending", 0.8, allocs, strategy_archetypes=archs)
    for a in plan.adjustments:
        assert a.rationale != ""
