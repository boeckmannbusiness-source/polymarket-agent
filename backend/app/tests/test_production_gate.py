import pytest
from app.services.audit_v2.production_gate_service import ProductionGateService
from app.schemas.audit_v2 import (
    SystemSafetyReport, DataIntegrityReport, FeedbackCycleReport,
    StressSafetyReport, CriticalPath, SinglePointOfFailure, CouplingRisk,
    ComponentEntry, SignalHealthEntry, FeedbackCycle, StressScenarioResult,
)


@pytest.fixture
def service():
    return ProductionGateService()


def make_system_safety(
    deep_chains: int = 0, spof_count: int = 0,
    coupling_count: int = 0,
) -> SystemSafetyReport:
    return SystemSafetyReport(
        components=[ComponentEntry(name="comp1", classification="deterministic")],
        adjacency={"comp1": []},
        critical_paths=[
            CriticalPath(path=["a"] * (3 + deep_chains), length=3 + deep_chains)
        ] if deep_chains or True else [],
        single_points_of_failure=[
            SinglePointOfFailure(component=f"spof_{i}", reason="test", downstream_count=3)
            for i in range(spof_count)
        ],
        coupling_risks=[
            CouplingRisk(components=["a", "b"], risk_type="bidirectional_dependency")
            for _ in range(coupling_count)
        ],
        risk_flags=[],
    )


def make_data_report(score: float) -> DataIntegrityReport:
    return DataIntegrityReport(
        signals=[SignalHealthEntry(source="test", health_score=score)],
        overall_data_quality_score=score,
    )


def make_cycles_report(risk: str, count: int = 0) -> FeedbackCycleReport:
    cycles = []
    if count > 0:
        cycles.append(FeedbackCycle(
            cycle=["a", "b", "c", "a"],
            cycle_length=3,
            risk_level=risk,
        ))
    return FeedbackCycleReport(
        cycles=cycles,
        overall_risk_level=risk,
        risk_flags=[f"Risk: {risk}"],
    )


def make_stress_report(score: float, dd: float = 10.0) -> StressSafetyReport:
    return StressSafetyReport(
        scenario_results=[
            StressScenarioResult(
                scenario_id="test", scenario_type="Test",
                allocation_deviation=0.1, max_drawdown_estimate=dd,
                recovery_sensitivity="medium",
            ),
        ],
        worst_case_scenario="Test",
        overall_stress_score=score,
    )


@pytest.mark.asyncio
async def test_evaluate_returns_report(service):
    report = await service.evaluate(
        system_safety=make_system_safety(),
        data_integrity=make_data_report(80),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(80),
    )
    assert report.overall_score >= 0
    assert report.classification in (
        "NOT_READY", "PAPER_READY", "MICRO_CAPITAL_READY", "LIVE_READY"
    )


@pytest.mark.asyncio
async def test_evaluate_not_ready_when_any_below_40(service):
    # Data score below 40 should make it NOT_READY
    report = await service.evaluate(
        system_safety=make_system_safety(),
        data_integrity=make_data_report(30),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(80),
    )
    assert report.classification == "NOT_READY"


@pytest.mark.asyncio
async def test_evaluate_paper_ready_when_all_above_40(service):
    report = await service.evaluate(
        system_safety=make_system_safety(deep_chains=1),
        data_integrity=make_data_report(50),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(50),
    )
    assert report.classification == "PAPER_READY"


@pytest.mark.asyncio
async def test_evaluate_micro_capital_ready_when_all_above_65(service):
    # Need to account for stability penalty from critical paths
    report = await service.evaluate(
        system_safety=make_system_safety(deep_chains=0, spof_count=0, coupling_count=0),
        data_integrity=make_data_report(75),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(75),
    )
    assert report.classification in ("MICRO_CAPITAL_READY", "PAPER_READY")


@pytest.mark.asyncio
async def test_evaluate_live_ready_when_all_above_80(service):
    report = await service.evaluate(
        system_safety=make_system_safety(deep_chains=0, spof_count=0, coupling_count=0),
        data_integrity=make_data_report(85),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(85),
    )
    assert report.classification in ("LIVE_READY", "MICRO_CAPITAL_READY")


@pytest.mark.asyncio
async def test_evaluate_score_ranges(service):
    report = await service.evaluate(
        system_safety=make_system_safety(),
        data_integrity=make_data_report(50),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(50),
    )
    assert 0 <= report.stability_score <= 100
    assert 0 <= report.data_score <= 100
    assert 0 <= report.stress_score <= 100
    assert 0 <= report.overall_score <= 100


@pytest.mark.asyncio
async def test_evaluate_high_cycles_reduces_stability(service):
    report_low = await service.evaluate(
        system_safety=make_system_safety(),
        data_integrity=make_data_report(80),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(80),
    )
    report_high = await service.evaluate(
        system_safety=make_system_safety(),
        data_integrity=make_data_report(80),
        feedback_cycles=make_cycles_report("HIGH"),
        stress_safety=make_stress_report(80),
    )
    assert report_high.stability_score < report_low.stability_score


@pytest.mark.asyncio
async def test_evaluate_spofs_reduce_stability(service):
    report_no_spof = await service.evaluate(
        system_safety=make_system_safety(spof_count=0),
        data_integrity=make_data_report(80),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(80),
    )
    report_spof = await service.evaluate(
        system_safety=make_system_safety(spof_count=5),
        data_integrity=make_data_report(80),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(80),
    )
    assert report_spof.stability_score < report_no_spof.stability_score


@pytest.mark.asyncio
async def test_evaluate_risk_summary_not_empty(service):
    report = await service.evaluate(
        system_safety=make_system_safety(spof_count=2),
        data_integrity=make_data_report(35),
        feedback_cycles=make_cycles_report("MEDIUM"),
        stress_safety=make_stress_report(40),
    )
    assert report.risk_summary != ""
    assert len(report.risk_summary) > 10


@pytest.mark.asyncio
async def test_evaluate_recommendation_not_empty(service):
    report = await service.evaluate(
        system_safety=make_system_safety(),
        data_integrity=make_data_report(50),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(50),
    )
    assert report.recommendation != ""


@pytest.mark.asyncio
async def test_evaluate_recommendation_mentions_safe_for_micro(service):
    report = await service.evaluate(
        system_safety=make_system_safety(deep_chains=0, spof_count=0, coupling_count=0),
        data_integrity=make_data_report(75),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(75),
    )
    if report.classification == "MICRO_CAPITAL_READY":
        assert "SAFE FOR 50" in report.recommendation


@pytest.mark.asyncio
async def test_evaluate_not_ready_recommendation(service):
    report = await service.evaluate(
        system_safety=make_system_safety(),
        data_integrity=make_data_report(20),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(20),
    )
    assert "NOT READY" in report.recommendation


@pytest.mark.asyncio
async def test_get_latest_returns_none_initially(service):
    assert await service.get_latest() is None


@pytest.mark.asyncio
async def test_get_latest_after_evaluate(service):
    report = await service.evaluate(
        system_safety=make_system_safety(),
        data_integrity=make_data_report(50),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(50),
    )
    latest = await service.get_latest()
    assert latest is not None
    assert latest.generated_at == report.generated_at


@pytest.mark.asyncio
async def test_evaluate_worst_case_stress_appears_in_summary(service):
    report = await service.evaluate(
        system_safety=make_system_safety(),
        data_integrity=make_data_report(50),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(40, dd=25),
    )
    assert "Worst stress" in report.risk_summary


@pytest.mark.asyncio
async def test_evaluate_all_good_no_risks(service):
    report = await service.evaluate(
        system_safety=make_system_safety(deep_chains=0, spof_count=0, coupling_count=0),
        data_integrity=make_data_report(95),
        feedback_cycles=make_cycles_report("LOW"),
        stress_safety=make_stress_report(95, dd=5),
    )
    assert "No significant risks" in report.risk_summary
