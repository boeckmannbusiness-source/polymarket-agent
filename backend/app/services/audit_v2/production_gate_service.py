from datetime import datetime, timezone

from app.schemas.audit_v2 import (
    ProductionGateReport, SystemSafetyReport, DataIntegrityReport,
    FeedbackCycleReport, StressSafetyReport,
)


class ProductionGateService:
    def __init__(self):
        self._latest: ProductionGateReport | None = None

    async def evaluate(
        self,
        system_safety: SystemSafetyReport,
        data_integrity: DataIntegrityReport,
        feedback_cycles: FeedbackCycleReport,
        stress_safety: StressSafetyReport,
    ) -> ProductionGateReport:
        stability_score = self._compute_stability_score(system_safety, feedback_cycles)
        data_score = data_integrity.overall_data_quality_score
        stress_score = stress_safety.overall_stress_score

        overall = round((stability_score * 0.35 + data_score * 0.30 + stress_score * 0.35), 1)
        classification = self._classify(stability_score, data_score, stress_score)
        risk_summary = self._build_risk_summary(
            stability_score, data_score, stress_score,
            system_safety, feedback_cycles, stress_safety,
        )
        recommendation = self._build_recommendation(classification, overall)

        report = ProductionGateReport(
            overall_score=overall,
            stability_score=round(stability_score, 1),
            data_score=round(data_score, 1),
            stress_score=round(stress_score, 1),
            classification=classification,
            risk_summary=risk_summary,
            recommendation=recommendation,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._latest = report
        return report

    def _compute_stability_score(
        self, system_safety: SystemSafetyReport,
        feedback_cycles: FeedbackCycleReport,
    ) -> float:
        score = 80.0

        # Penalty for deep dependency chains
        deep_chains = sum(1 for cp in system_safety.critical_paths if cp.length > 3)
        score -= deep_chains * 10

        # Penalty for SPOFs
        score -= len(system_safety.single_points_of_failure) * 5

        # Penalty for coupling risks
        score -= len(system_safety.coupling_risks) * 8

        # Penalty for feedback cycles
        if feedback_cycles.overall_risk_level == "HIGH":
            score -= 25
        elif feedback_cycles.overall_risk_level == "MEDIUM":
            score -= 10

        return max(0, min(100, score))

    def _classify(self, stability: float, data: float, stress: float) -> str:
        if stability < 40 or data < 40 or stress < 40:
            return "NOT_READY"
        if stability >= 80 and data >= 80 and stress >= 80:
            return "LIVE_READY"
        if stability >= 65 and data >= 65 and stress >= 65:
            return "MICRO_CAPITAL_READY"
        if stability >= 40 and data >= 40 and stress >= 40:
            return "PAPER_READY"
        return "NOT_READY"

    def _build_risk_summary(
        self, stability: float, data: float, stress: float,
        system_safety: SystemSafetyReport,
        feedback_cycles: FeedbackCycleReport,
        stress_safety: StressSafetyReport,
    ) -> str:
        parts: list[str] = []

        if stability < 65:
            parts.append(f"Structural stability is {stability:.0f}/100")

        if data < 65:
            parts.append(f"Data quality is {data:.0f}/100")

        if stress < 65:
            parts.append(f"Stress tolerance is {stress:.0f}/100")

        if system_safety.single_points_of_failure:
            spof_names = [s.component for s in system_safety.single_points_of_failure[:3]]
            parts.append(f"SPOFs detected: {', '.join(spof_names)}")

        if feedback_cycles.overall_risk_level == "HIGH":
            parts.append("High-risk feedback cycles present")
        elif feedback_cycles.overall_risk_level == "MEDIUM":
            parts.append("Medium-risk indirect cycles detected")

        if stress_safety.worst_case_scenario and stress < 80:
            worst = stress_safety.worst_case_scenario
            worst_result = next(
                (r for r in stress_safety.scenario_results
                 if r.scenario_type == worst), None
            )
            if worst_result:
                parts.append(
                    f"Worst stress: {worst} "
                    f"({worst_result.max_drawdown_estimate:.1f}% drawdown)"
                )

        if not parts:
            parts.append("No significant risks detected")

        return "; ".join(parts)

    def _build_recommendation(self, classification: str, overall: float) -> str:
        if classification == "LIVE_READY":
            return (
                f"System scores {overall}/100 — technically LIVE_READY, "
                f"but micro-capital validation strongly recommended before full deployment"
            )
        elif classification == "MICRO_CAPITAL_READY":
            return (
                f"System scores {overall}/100 — SAFE FOR 50-100€ LIVE TEST. "
                f"All safety gates pass minimum thresholds."
            )
        elif classification == "PAPER_READY":
            return (
                f"System scores {overall}/100 — NOT SAFE for live capital. "
                f"Paper trading only until all dimensions exceed 65."
            )
        else:
            return (
                f"System scores {overall}/100 — NOT READY for any deployment. "
                f"Critical safety gaps must be resolved first."
            )

    async def get_latest(self) -> ProductionGateReport | None:
        return self._latest


production_gate_service = ProductionGateService()
