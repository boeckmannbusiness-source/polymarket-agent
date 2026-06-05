import pytest
from app.services.research.autonomous_research_pipeline import pipeline


class TestAutonomousResearchPipeline:
    @pytest.mark.asyncio
    async def test_run_returns_report(self):
        report = await pipeline.run(market_data={"volatility": 0.3, "trend_strength": 0.6})
        assert report.report_id
        assert report.generated_at
        assert report.summary
        assert len(report.candidates) >= 0
        assert len(report.regimes) >= 1

    @pytest.mark.asyncio
    async def test_run_generates_candidates(self):
        report = await pipeline.run(market_data={"volatility": 0.2, "trend_strength": 0.1})
        assert len(report.candidates) >= 4  # mutated + recombined + contrarian + regime + novel

    @pytest.mark.asyncio
    async def test_run_includes_regime(self):
        report = await pipeline.run(market_data={"volatility": 0.5})
        assert report.regimes[0].regime == "high_volatility"

    @pytest.mark.asyncio
    async def test_run_includes_hypotheses(self):
        report = await pipeline.run()
        assert len(report.hypotheses) >= 2

    @pytest.mark.asyncio
    async def test_get_reports(self):
        reports = await pipeline.get_reports()
        assert isinstance(reports, list)
        assert len(reports) >= 0

    @pytest.mark.asyncio
    async def test_get_latest_report(self):
        report = await pipeline.get_latest_report()
        assert report is None or report.report_id

    @pytest.mark.asyncio
    async def test_get_candidate_recommendations(self):
        candidates = await pipeline.get_candidate_recommendations()
        assert isinstance(candidates, list)

    @pytest.mark.asyncio
    async def test_run_deterministic_with_empty_data(self):
        report = await pipeline.run(market_data={})
        assert report.report_id
        assert len(report.regimes) == 1
