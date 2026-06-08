from datetime import datetime, timezone
from typing import Any

from app.schemas.audit_v2 import StressSafetyReport, StressScenarioResult


class StressSafetySimulator:
    SCENARIOS = [
        "regime_misclassification",
        "correlation_shock",
        "volatility_spike",
    ]

    def __init__(self):
        self._latest: StressSafetyReport | None = None

    async def simulate(
        self,
        baseline_allocations: dict[str, float] | None = None,
        correlation_matrix: dict[str, dict[str, float]] | None = None,
        return_variances: dict[str, float] | None = None,
    ) -> StressSafetyReport:
        baseline = baseline_allocations or {"strat_a": 0.3, "strat_b": 0.3,
                                            "strat_c": 0.2, "strat_d": 0.2}
        corr = correlation_matrix or self._default_correlation()
        variances = return_variances or {"strat_a": 0.04, "strat_b": 0.06,
                                         "strat_c": 0.03, "strat_d": 0.05}

        results: list[StressScenarioResult] = []
        risk_flags: list[str] = []

        # Scenario 1: Regime Misclassification
        r1 = self._simulate_regime_misclassification(baseline)
        results.append(r1)

        # Scenario 2: Correlation Shock
        r2 = self._simulate_correlation_shock(baseline, corr)
        results.append(r2)

        # Scenario 3: Volatility Spike
        r3 = self._simulate_volatility_spike(baseline, variances)
        results.append(r3)

        for r in results:
            if r.max_drawdown_estimate > 15:
                risk_flags.append(
                    f"High drawdown risk in {r.scenario_type}: "
                    f"{r.max_drawdown_estimate:.1f}%"
                )

        worst = max(results, key=lambda r: r.max_drawdown_estimate)
        stress_score = self._compute_stress_score(results)

        report = StressSafetyReport(
            scenario_results=results,
            worst_case_scenario=worst.scenario_type,
            overall_stress_score=round(stress_score, 1),
            risk_flags=risk_flags,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._latest = report
        return report

    def _default_correlation(self) -> dict[str, dict[str, float]]:
        strats = ["strat_a", "strat_b", "strat_c", "strat_d"]
        corr = {}
        for s in strats:
            corr[s] = {}
            for t in strats:
                if s == t:
                    corr[s][t] = 1.0
                else:
                    corr[s][t] = 0.3
        return corr

    def _simulate_regime_misclassification(
        self, baseline: dict[str, float]
    ) -> StressScenarioResult:
        # Wrong regime flips momentum and reversion allocations
        deviation = 0.0
        worst_dd = 0.0
        details: dict[str, Any] = {}

        for strat, alloc in baseline.items():
            if "momentum" in strat.lower() or "trend" in strat.lower():
                expected = alloc * 0.5  # should reduce in wrong regime
                actual = alloc * 1.2  # but we increased
                deviation += abs(actual - expected)
                worst_dd = max(worst_dd, abs(actual - expected) * 25)
                details[strat] = {
                    "expected": round(expected, 4),
                    "actual": round(actual, 4),
                    "delta": round(actual - expected, 4),
                }
            elif "reversion" in strat.lower() or "contrarian" in strat.lower():
                expected = alloc * 1.2
                actual = alloc * 0.5
                deviation += abs(actual - expected)
                worst_dd = max(worst_dd, abs(actual - expected) * 20)
                details[strat] = {
                    "expected": round(expected, 4),
                    "actual": round(actual, 4),
                    "delta": round(actual - expected, 4),
                }

        if not details:
            # Generic estimate for unknown strategies
            deviation = sum(baseline.values()) * 0.3
            worst_dd = 8.0
            details["generic"] = {"note": "no strategy-specific archetypes detected"}

        recovery_sensitivity = "high" if worst_dd > 15 else "medium"

        return StressScenarioResult(
            scenario_id="regime_misclassification",
            scenario_type="Regime Misclassification",
            allocation_deviation=round(deviation, 4),
            max_drawdown_estimate=round(worst_dd, 2),
            recovery_sensitivity=recovery_sensitivity,
            details=details,
        )

    def _simulate_correlation_shock(
        self, baseline: dict[str, float],
        correlation_matrix: dict[str, dict[str, float]],
    ) -> StressScenarioResult:
        n = len(baseline)
        if n < 2:
            return StressScenarioResult(
                scenario_id="correlation_shock",
                scenario_type="Correlation Shock",
                allocation_deviation=0.0,
                max_drawdown_estimate=5.0,
                recovery_sensitivity="medium",
                details={"note": "insufficient strategies for correlation analysis"},
            )

        avg_corr = self._average_correlation(correlation_matrix, list(baseline.keys()))
        shocked_corr = min(1.0, avg_corr * 3.0)

        # Higher correlation = less diversification = higher drawdown
        diversification_loss = (shocked_corr - avg_corr) / max(0.01, avg_corr)
        deviation = diversification_loss * 0.15
        max_dd = 5.0 + diversification_loss * 15.0

        recovery_sensitivity = "high" if max_dd > 20 else "medium"

        return StressScenarioResult(
            scenario_id="correlation_shock",
            scenario_type="Correlation Shock",
            allocation_deviation=round(deviation, 4),
            max_drawdown_estimate=round(min(max_dd, 50), 2),
            recovery_sensitivity=recovery_sensitivity,
            details={
                "original_avg_correlation": round(avg_corr, 4),
                "shocked_correlation": round(shocked_corr, 4),
                "diversification_loss_pct": round(diversification_loss * 100, 1),
            },
        )

    def _simulate_volatility_spike(
        self, baseline: dict[str, float],
        return_variances: dict[str, float],
    ) -> StressScenarioResult:
        if not return_variances:
            return StressScenarioResult(
                scenario_id="volatility_spike",
                scenario_type="Volatility Spike",
                allocation_deviation=0.0,
                max_drawdown_estimate=10.0,
                recovery_sensitivity="medium",
                details={"note": "no variance data available"},
            )

        avg_variance = sum(return_variances.values()) / max(len(return_variances), 1)
        shocked_variance = avg_variance * 5.0
        vol_ratio = (shocked_variance ** 0.5) / (avg_variance ** 0.5)

        deviation = (vol_ratio - 1.0) * 0.1
        max_dd = 5.0 + (vol_ratio - 1.0) * 10.0

        recovery_sensitivity = "high" if max_dd > 20 else "medium"

        return StressScenarioResult(
            scenario_id="volatility_spike",
            scenario_type="Volatility Spike",
            allocation_deviation=round(deviation, 4),
            max_drawdown_estimate=round(min(max_dd, 50), 2),
            recovery_sensitivity=recovery_sensitivity,
            details={
                "original_avg_volatility": round(avg_variance ** 0.5, 4),
                "shocked_volatility": round(shocked_variance ** 0.5, 4),
                "volatility_multiplier": round(vol_ratio, 2),
            },
        )

    def _average_correlation(
        self, corr: dict[str, dict[str, float]],
        strategies: list[str],
    ) -> float:
        values = []
        for i, s in enumerate(strategies):
            for t in strategies[i + 1:]:
                if s in corr and t in corr[s]:
                    values.append(abs(corr[s][t]))
        if not values:
            return 0.3
        return sum(values) / len(values)

    def _compute_stress_score(self, results: list[StressScenarioResult]) -> float:
        if not results:
            return 100.0
        dd_penalty = sum(r.max_drawdown_estimate for r in results) / len(results)
        score = max(0, 100 - dd_penalty * 2.5)
        return score

    async def get_latest(self) -> StressSafetyReport | None:
        return self._latest


stress_safety_simulator = StressSafetySimulator()
