from datetime import datetime, timezone
from typing import Any

from app.schemas.audit_v2 import DataIntegrityReport, SignalHealthEntry


class DataIntegrityAuditService:
    def __init__(self):
        self._latest: DataIntegrityReport | None = None

    async def audit(
        self,
        signal_sources: dict[str, dict[str, Any]] | None = None,
    ) -> DataIntegrityReport:
        if signal_sources is None:
            sources = self._get_default_sources()
        else:
            sources = signal_sources
        signals: list[SignalHealthEntry] = []
        risk_flags: list[str] = []

        for source_name, data in sources.items():
            freshness_hours = data.get("age_hours", 999.0)
            stability = data.get("stability", 0.5)
            missingness = data.get("missingness_pct", 0.0)
            source_type = data.get("source_type", "internal_computed")

            health_score = self._compute_health_score(
                freshness_hours, stability, missingness, source_type
            )

            if health_score < 40:
                risk_flags.append(
                    f"Low signal health for {source_name}: {health_score:.1f}/100"
                )
            if freshness_hours > 48:
                risk_flags.append(
                    f"Stale data: {source_name} last updated {freshness_hours:.0f}h ago"
                )
            if missingness > 20:
                risk_flags.append(
                    f"High missingness in {source_name}: {missingness:.0f}%"
                )

            signals.append(SignalHealthEntry(
                source=source_name,
                freshness_hours=round(freshness_hours, 2),
                stability_score=round(stability, 2),
                missingness_pct=round(missingness, 1),
                source_type=source_type,
                health_score=round(health_score, 1),
            ))

        overall_score = self._compute_overall_score(signals)

        report = DataIntegrityReport(
            signals=signals,
            overall_data_quality_score=round(overall_score, 1),
            risk_flags=risk_flags,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._latest = report
        return report

    def _get_default_sources(self) -> dict[str, dict[str, Any]]:
        return {
            "portfolio_intelligence": {
                "age_hours": 6.0, "stability": 0.85,
                "missingness_pct": 2.0, "source_type": "internal_computed",
            },
            "regime_classification": {
                "age_hours": 1.0, "stability": 0.70,
                "missingness_pct": 0.0, "source_type": "internal_computed",
            },
            "strategy_performance": {
                "age_hours": 12.0, "stability": 0.60,
                "missingness_pct": 5.0, "source_type": "internal_computed",
            },
            "market_correlations": {
                "age_hours": 24.0, "stability": 0.50,
                "missingness_pct": 10.0, "source_type": "internal_computed",
            },
            "regime_expected_returns": {
                "age_hours": 6.0, "stability": 0.75,
                "missingness_pct": 3.0, "source_type": "internal_computed",
            },
            "monte_carlo_simulation": {
                "age_hours": 24.0, "stability": 0.40,
                "missingness_pct": 0.0, "source_type": "synthetic",
            },
            "allocation_learning": {
                "age_hours": 12.0, "stability": 0.55,
                "missingness_pct": 8.0, "source_type": "adaptive",
            },
            "volatility_estimates": {
                "age_hours": 1.0, "stability": 0.45,
                "missingness_pct": 0.0, "source_type": "external_derived",
            },
        }

    def _compute_health_score(
        self, freshness_hours: float, stability: float,
        missingness_pct: float, source_type: str,
    ) -> float:
        freshness_score = max(0, 100 - freshness_hours * 2)
        if freshness_hours > 48:
            freshness_score = max(0, 100 - freshness_hours * 4)

        stability_score = stability * 100
        completeness_score = 100 - missingness_pct

        type_penalty = 0.0
        if source_type == "synthetic":
            type_penalty = 15.0
        elif source_type == "external_derived":
            type_penalty = 10.0
        elif source_type == "adaptive":
            type_penalty = 5.0

        score = (
            freshness_score * 0.35 +
            stability_score * 0.25 +
            completeness_score * 0.25 -
            type_penalty * 0.15
        )
        return max(0, min(100, score))

    def _compute_overall_score(self, signals: list[SignalHealthEntry]) -> float:
        if not signals:
            return 0.0
        scores = [s.health_score for s in signals]
        weighted = sum(s.health_score * self._source_weight(s.source_type) for s in signals)
        total_weight = sum(self._source_weight(s.source_type) for s in signals)
        if total_weight == 0:
            return sum(scores) / len(scores)
        return weighted / total_weight

    def _source_weight(self, source_type: str) -> float:
        weights = {
            "internal_computed": 1.5,
            "external_derived": 1.0,
            "synthetic": 0.5,
            "adaptive": 0.8,
        }
        return weights.get(source_type, 1.0)

    async def get_latest(self) -> DataIntegrityReport | None:
        return self._latest


data_integrity_audit_service = DataIntegrityAuditService()
