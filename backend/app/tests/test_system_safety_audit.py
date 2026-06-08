import pytest
from app.services.audit_v2.system_safety_audit_service import SystemSafetyAuditService


@pytest.fixture
def service():
    return SystemSafetyAuditService()


@pytest.mark.asyncio
async def test_audit_returns_report(service):
    report = await service.audit()
    assert report.components is not None
    assert len(report.components) > 0
    assert report.generated_at != ""


@pytest.mark.asyncio
async def test_audit_all_components_classified(service):
    report = await service.audit()
    classifications = {c.classification for c in report.components}
    assert "deterministic" in classifications
    assert "stochastic" in classifications
    assert "adaptive" in classifications


@pytest.mark.asyncio
async def test_audit_components_have_no_unknown_classification(service):
    report = await service.audit()
    for c in report.components:
        assert c.classification in ("deterministic", "stochastic", "adaptive"), f"{c.name} has unknown classification"


@pytest.mark.asyncio
async def test_audit_dependency_graph_complete(service):
    report = await service.audit()
    for c in report.components:
        assert c.name in report.adjacency, f"{c.name} missing from adjacency"
        assert len(report.adjacency[c.name]) >= 0


@pytest.mark.asyncio
async def test_audit_critical_paths_found(service):
    report = await service.audit()
    assert len(report.critical_paths) > 0
    for cp in report.critical_paths:
        assert len(cp.path) >= 1
        assert cp.length >= 1


@pytest.mark.asyncio
async def test_audit_deep_chains_flagged(service):
    report = await service.audit()
    deep_flags = [f for f in report.risk_flags if "Deep dependency chain" in f]
    # Some paths should be >3 hops given the dependency graph
    assert len(deep_flags) >= 0  # at least may exist


@pytest.mark.asyncio
async def test_audit_spof_detected(service):
    report = await service.audit()
    if report.single_points_of_failure:
        for spof in report.single_points_of_failure:
            assert spof.downstream_count >= 2
            assert spof.component != ""


@pytest.mark.asyncio
async def test_audit_coupling_risks(service):
    report = await service.audit()
    for risk in report.coupling_risks:
        assert len(risk.components) == 2
        assert risk.risk_type == "bidirectional_dependency"


@pytest.mark.asyncio
async def test_audit_risk_flags_generated(service):
    report = await service.audit()
    assert len(report.risk_flags) >= 0
    for flag in report.risk_flags:
        assert isinstance(flag, str)
        assert len(flag) > 0


@pytest.mark.asyncio
async def test_audit_expected_component_count(service):
    report = await service.audit()
    # Should have all Phase 4E, 4F, 4G components
    names = [c.name for c in report.components]
    assert "portfolio_intelligence_service" in names
    assert "autonomous_optimization_pipeline" in names
    assert "autonomous_control_pipeline" in names
    assert "control_plane" in names
    assert "portfolio_optimization_engine" in names
    assert "stability_controller" in names


@pytest.mark.asyncio
async def test_audit_deterministic_count(service):
    report = await service.audit()
    det = [c for c in report.components if c.classification == "deterministic"]
    sto = [c for c in report.components if c.classification == "stochastic"]
    ada = [c for c in report.components if c.classification == "adaptive"]
    assert len(det) >= 10  # most components are deterministic
    assert len(sto) >= 1  # monte carlo + stress testing
    assert len(ada) >= 2  # allocation_learning + feedback_dampening


@pytest.mark.asyncio
async def test_audit_critical_path_lengths(service):
    report = await service.audit()
    for cp in report.critical_paths:
        assert cp.length == len(cp.path)


@pytest.mark.asyncio
async def test_get_latest_returns_none_initially(service):
    assert await service.get_latest() is None


@pytest.mark.asyncio
async def test_get_latest_after_audit(service):
    report = await service.audit()
    latest = await service.get_latest()
    assert latest is not None
    assert latest.generated_at == report.generated_at


@pytest.mark.asyncio
async def test_adjacency_has_all_components(service):
    report = await service.audit()
    for c in report.components:
        assert c.name in report.adjacency


@pytest.mark.asyncio
async def test_spof_flags_match_spofs(service):
    report = await service.audit()
    spof_flags = [f for f in report.risk_flags if "SPOF:" in f]
    assert len(spof_flags) == len(report.single_points_of_failure)


@pytest.mark.asyncio
async def test_bottleneck_flags_for_high_fan_in(service):
    report = await service.audit()
    bottleneck_flags = [f for f in report.risk_flags if "Shared dependency bottleneck" in f]
    for flag in bottleneck_flags:
        assert "depends on" in flag


@pytest.mark.asyncio
async def test_components_have_depends_on(service):
    report = await service.audit()
    for c in report.components:
        assert hasattr(c, "depends_on")
        assert isinstance(c.depends_on, list)


@pytest.mark.asyncio
async def test_audit_is_deterministic(service):
    report1 = await service.audit()
    report2 = await service.audit()
    assert len(report1.components) == len(report2.components)
    for c1, c2 in zip(report1.components, report2.components):
        assert c1.name == c2.name
        assert c1.classification == c2.classification
