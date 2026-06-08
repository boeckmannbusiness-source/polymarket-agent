import pytest
from app.services.audit_v2.data_integrity_audit_service import DataIntegrityAuditService


@pytest.fixture
def service():
    return DataIntegrityAuditService()


@pytest.mark.asyncio
async def test_audit_returns_report_with_defaults(service):
    report = await service.audit()
    assert report.signals is not None
    assert len(report.signals) > 0
    assert report.generated_at != ""


@pytest.mark.asyncio
async def test_audit_all_sources_have_health_scores(service):
    report = await service.audit()
    for sig in report.signals:
        assert 0 <= sig.health_score <= 100
        assert sig.source != ""


@pytest.mark.asyncio
async def test_audit_health_score_computation_fresh_data(service):
    sources = {
        "test_source": {
            "age_hours": 1.0, "stability": 0.95,
            "missingness_pct": 1.0, "source_type": "internal_computed",
        },
    }
    report = await service.audit(signal_sources=sources)
    assert len(report.signals) == 1
    assert report.signals[0].health_score > 80


@pytest.mark.asyncio
async def test_audit_health_score_computation_stale_data(service):
    sources = {
        "test_source": {
            "age_hours": 100.0, "stability": 0.95,
            "missingness_pct": 1.0, "source_type": "internal_computed",
        },
    }
    report = await service.audit(signal_sources=sources)
    assert report.signals[0].health_score < 50


@pytest.mark.asyncio
async def test_audit_health_score_computation_high_missingness(service):
    sources = {
        "test_source": {
            "age_hours": 1.0, "stability": 0.95,
            "missingness_pct": 80.0, "source_type": "internal_computed",
        },
    }
    report = await service.audit(signal_sources=sources)
    assert report.signals[0].health_score < 70


@pytest.mark.asyncio
async def test_audit_synthetic_source_penalty(service):
    sources = {
        "synth": {"age_hours": 1.0, "stability": 0.95,
                  "missingness_pct": 1.0, "source_type": "synthetic"},
        "internal": {"age_hours": 1.0, "stability": 0.95,
                     "missingness_pct": 1.0, "source_type": "internal_computed"},
    }
    report = await service.audit(signal_sources=sources)
    synth_score = next(s.health_score for s in report.signals if s.source == "synth")
    internal_score = next(s.health_score for s in report.signals if s.source == "internal")
    assert synth_score < internal_score


@pytest.mark.asyncio
async def test_audit_risk_flags_for_stale_data(service):
    sources = {
        "stale_source": {
            "age_hours": 100.0, "stability": 0.5,
            "missingness_pct": 5.0, "source_type": "internal_computed",
        },
    }
    report = await service.audit(signal_sources=sources)
    assert any("Stale" in f for f in report.risk_flags)


@pytest.mark.asyncio
async def test_audit_risk_flags_for_high_missingness(service):
    sources = {
        "missing_source": {
            "age_hours": 1.0, "stability": 0.5,
            "missingness_pct": 50.0, "source_type": "internal_computed",
        },
    }
    report = await service.audit(signal_sources=sources)
    assert any("High missingness" in f for f in report.risk_flags)


@pytest.mark.asyncio
async def test_audit_overall_score_aggregation(service):
    report = await service.audit()
    assert 0 <= report.overall_data_quality_score <= 100


@pytest.mark.asyncio
async def test_audit_overall_score_with_all_perfect(service):
    sources = {
        "s1": {"age_hours": 0.0, "stability": 1.0,
               "missingness_pct": 0.0, "source_type": "internal_computed"},
        "s2": {"age_hours": 0.0, "stability": 1.0,
               "missingness_pct": 0.0, "source_type": "internal_computed"},
    }
    report = await service.audit(signal_sources=sources)
    assert report.overall_data_quality_score > 80


@pytest.mark.asyncio
async def test_audit_overall_score_with_all_bad(service):
    sources = {
        "s1": {"age_hours": 100.0, "stability": 0.0,
               "missingness_pct": 100.0, "source_type": "synthetic"},
    }
    report = await service.audit(signal_sources=sources)
    assert report.overall_data_quality_score < 30


@pytest.mark.asyncio
async def test_audit_source_types_present(service):
    report = await service.audit()
    types = {s.source_type for s in report.signals}
    assert "internal_computed" in types
    assert "synthetic" in types or "external_derived" in types


@pytest.mark.asyncio
async def test_audit_freshness_hours_recorded(service):
    sources = {
        "test": {"age_hours": 12.5, "stability": 0.8,
                 "missingness_pct": 2.0, "source_type": "internal_computed"},
    }
    report = await service.audit(signal_sources=sources)
    assert report.signals[0].freshness_hours == 12.5


@pytest.mark.asyncio
async def test_audit_stability_score_recorded(service):
    sources = {
        "test": {"age_hours": 1.0, "stability": 0.75,
                 "missingness_pct": 2.0, "source_type": "internal_computed"},
    }
    report = await service.audit(signal_sources=sources)
    assert report.signals[0].stability_score == 0.75


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
async def test_audit_handles_empty_sources(service):
    report = await service.audit(signal_sources={})
    assert len(report.signals) == 0
    assert report.overall_data_quality_score == 0.0


@pytest.mark.asyncio
async def test_audit_risk_flags_empty_for_healthy(service):
    sources = {
        "healthy": {"age_hours": 0.5, "stability": 0.99,
                    "missingness_pct": 0.0, "source_type": "internal_computed"},
    }
    report = await service.audit(signal_sources=sources)
    assert len(report.risk_flags) == 0
