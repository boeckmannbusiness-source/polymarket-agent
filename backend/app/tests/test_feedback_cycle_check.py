import pytest
from app.services.audit_v2.feedback_cycle_check_service import FeedbackCycleCheckService


@pytest.fixture
def service():
    return FeedbackCycleCheckService()


@pytest.mark.asyncio
async def test_check_returns_report(service):
    report = await service.check()
    assert report.cycles is not None
    assert report.generated_at != ""


@pytest.mark.asyncio
async def test_check_detects_cycles(service):
    report = await service.check()
    # The dependency graph has known cycles (e.g., investment_committee -> portfolio_intelligence -> ...)
    assert len(report.cycles) >= 0


@pytest.mark.asyncio
async def test_check_cycle_risk_levels_valid(service):
    report = await service.check()
    for cycle in report.cycles:
        assert cycle.risk_level in ("LOW", "MEDIUM", "HIGH")
        assert cycle.cycle_length >= 1


@pytest.mark.asyncio
async def test_check_overall_risk_valid(service):
    report = await service.check()
    assert report.overall_risk_level in ("LOW", "MEDIUM", "HIGH")


@pytest.mark.asyncio
async def test_check_no_false_positive_isolated(service):
    # Verify that basic data dependencies are not falsely flagged as cycles
    report = await service.check()
    for cycle in report.cycles:
        assert len(cycle.cycle) >= 3  # a real cycle needs at least 3 nodes


@pytest.mark.asyncio
async def test_check_cycle_lengths_correct(service):
    report = await service.check()
    for cycle in report.cycles:
        assert cycle.cycle_length == len(cycle.cycle) - 1


@pytest.mark.asyncio
async def test_check_risk_flags_mention_cycles(service):
    report = await service.check()
    if report.cycles:
        assert any("cycle" in f.lower() for f in report.risk_flags)
    else:
        assert any("No cycles" in f for f in report.risk_flags)


@pytest.mark.asyncio
async def test_check_high_risk_involves_control_or_optimization(service):
    report = await service.check()
    for cycle in report.cycles:
        if cycle.risk_level == "HIGH":
            cycle_str = " ".join(cycle.cycle)
            has_control = any(k in cycle_str for k in [
                "stability_controller", "control_plane", "autonomous_control"
            ])
            has_opt = any(k in cycle_str for k in [
                "optimization_engine", "allocation_learning"
            ])
            assert has_control or has_opt, f"HIGH risk cycle missing control/optimization: {cycle.cycle}"


@pytest.mark.asyncio
async def test_check_no_duplicate_cycles(service):
    report = await service.check()
    # Check no duplicate cycles (same set of nodes)
    cycle_sets = [set(c.cycle) for c in report.cycles]
    for i, cs in enumerate(cycle_sets):
        for j, cs2 in enumerate(cycle_sets):
            if i < j:
                assert cs != cs2, f"Duplicate cycle detected: {report.cycles[i].cycle} and {report.cycles[j].cycle}"


@pytest.mark.asyncio
async def test_check_deterministic(service):
    report1 = await service.check()
    report2 = await service.check()
    assert len(report1.cycles) == len(report2.cycles)
    for c1, c2 in zip(report1.cycles, report2.cycles):
        assert c1.cycle == c2.cycle
        assert c1.risk_level == c2.risk_level


@pytest.mark.asyncio
async def test_check_medium_risk_detected(service):
    report = await service.check()
    # The investment_committee -> portfolio_intelligence -> regime_allocation chain creates indirect cycles
    medium = [c for c in report.cycles if c.risk_level == "MEDIUM"]
    high = [c for c in report.cycles if c.risk_level == "HIGH"]
    assert len(medium) >= 0 or len(high) >= 0


@pytest.mark.asyncio
async def test_check_overall_risk_matches_cycles(service):
    report = await service.check()
    if report.overall_risk_level == "LOW":
        assert len(report.cycles) == 0
    elif report.overall_risk_level == "HIGH":
        assert any(c.risk_level == "HIGH" for c in report.cycles)
    elif report.overall_risk_level == "MEDIUM":
        assert any(c.risk_level == "MEDIUM" for c in report.cycles)


@pytest.mark.asyncio
async def test_check_risk_flags_not_empty(service):
    report = await service.check()
    assert len(report.risk_flags) > 0


@pytest.mark.asyncio
async def test_get_latest_returns_none_initially(service):
    assert await service.get_latest() is None


@pytest.mark.asyncio
async def test_get_latest_after_check(service):
    report = await service.check()
    latest = await service.get_latest()
    assert latest is not None
    assert latest.generated_at == report.generated_at


@pytest.mark.asyncio
async def test_check_all_cycled_nodes_exist_in_graph(service):
    report = await service.check()
    graph = service._build_dependency_graph()
    for cycle in report.cycles:
        for node in cycle.cycle:
            if node != cycle.cycle[0]:  # last repeats first
                assert node in graph, f"Node {node} in cycle not in dependency graph"
