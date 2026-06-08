from datetime import datetime, timezone
from typing import Any

from app.schemas.audit_v2 import (
    SystemSafetyReport, ComponentEntry, CriticalPath,
    SinglePointOfFailure, CouplingRisk,
)


class SystemSafetyAuditService:
    def __init__(self):
        self._latest: SystemSafetyReport | None = None

    async def audit(self) -> SystemSafetyReport:
        components, adjacency = self._build_component_graph()
        critical_paths = self._find_critical_paths(adjacency)
        spofs = self._find_single_points_of_failure(adjacency)
        coupling_risks = self._find_coupling_risks(adjacency, components)
        risk_flags = self._generate_risk_flags(critical_paths, spofs, adjacency)

        report = SystemSafetyReport(
            components=components,
            adjacency=adjacency,
            critical_paths=critical_paths,
            single_points_of_failure=spofs,
            coupling_risks=coupling_risks,
            risk_flags=risk_flags,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._latest = report
        return report

    def _build_component_graph(self) -> tuple[list[ComponentEntry], dict[str, list[str]]]:
        entries: list[ComponentEntry] = []
        adjacency: dict[str, list[str]] = {}

        components = {
            # Phase 4E — Intelligence
            "portfolio_intelligence_service": ("deterministic", [
                "tournament_rankings", "strategy_performance", "regime_data",
            ]),
            "resilience_service": ("deterministic", [
                "allocations", "strategy_correlations", "regime_exposure",
            ]),
            "stress_testing_service": ("stochastic", [
                "strategy_health", "allocations",
            ]),
            "investment_committee_service": ("deterministic", [
                "portfolio_intelligence_service", "resilience_service",
                "regime_allocation_service", "stress_testing_service",
            ]),
            "regime_allocation_service": ("deterministic", [
                "regime_data", "strategy_archetypes",
            ]),
            "autonomous_portfolio_review": ("deterministic", [
                "portfolio_intelligence_service", "regime_allocation_service",
                "stress_testing_service", "resilience_service",
                "investment_committee_service",
            ]),
            # Phase 4F — Optimization
            "regime_expected_return_model": ("deterministic", [
                "regime_probabilities", "strategy_performance_by_regime",
            ]),
            "risk_model_service": ("deterministic", [
                "strategy_ids", "base_correlations", "regime",
            ]),
            "portfolio_optimization_engine": ("deterministic", [
                "regime_expected_return_model", "risk_model_service",
            ]),
            "monte_carlo_simulation_service": ("stochastic", [
                "risk_model_service", "expected_returns",
            ]),
            "allocation_learning_service": ("adaptive", [
                "portfolio_optimization_engine", "actual_returns",
                "regime_accuracy",
            ]),
            "autonomous_optimization_pipeline": ("deterministic", [
                "regime_expected_return_model", "risk_model_service",
                "portfolio_optimization_engine", "monte_carlo_simulation_service",
                "allocation_learning_service",
            ]),
            # Phase 4G — Control
            "stability_controller": ("deterministic", [
                "portfolio_optimization_engine", "current_weights",
            ]),
            "feedback_dampening_service": ("adaptive", [
                "learning_signals", "volatility_estimate",
            ]),
            "portfolio_drift_detector": ("deterministic", [
                "current_weights", "equilibrium_weights",
                "covariance_matrices",
            ]),
            "regime_transition_controller": ("deterministic", [
                "regime_probabilities", "volatility_shock",
            ]),
            "control_plane": ("deterministic", [
                "trading_enabled", "execution_mode",
            ]),
            "autonomous_control_pipeline": ("deterministic", [
                "stability_controller", "feedback_dampening_service",
                "portfolio_drift_detector", "regime_transition_controller",
            ]),
        }

        for name, (classification, deps) in components.items():
            entry = ComponentEntry(
                name=name,
                classification=classification,
                depends_on=deps,
            )
            entries.append(entry)
            adjacency[name] = list(deps)

        return entries, adjacency

    def _find_critical_paths(self, adjacency: dict[str, list[str]]) -> list[CriticalPath]:
        def dfs(node: str, visited: set[str], path: list[str]) -> list[list[str]]:
            if node not in adjacency or not adjacency[node]:
                return [list(path)]
            paths = []
            for dep in adjacency[node]:
                dep_name = dep if isinstance(dep, str) else dep
                if dep_name not in visited:
                    visited.add(dep_name)
                    path.append(dep_name)
                    paths.extend(dfs(dep_name, visited, path))
                    path.pop()
                    visited.discard(dep_name)
            return paths if paths else [list(path)]

        all_paths = []
        for node in adjacency:
            all_paths.extend(dfs(node, {node}, [node]))

        if not all_paths:
            if adjacency:
                all_paths = [[n] for n in adjacency]

        unique_paths: dict[str, list[str]] = {}
        for p in all_paths:
            key = "->".join(p)
            if key not in unique_paths or len(p) > len(unique_paths[key]):
                unique_paths[key] = p

        sorted_paths = sorted(unique_paths.values(), key=len, reverse=True)
        top3 = [CriticalPath(path=p, length=len(p)) for p in sorted_paths[:3]]
        return top3

    def _find_single_points_of_failure(
        self, adjacency: dict[str, list[str]]
    ) -> list[SinglePointOfFailure]:
        downstream_count: dict[str, int] = {}
        for node, deps in adjacency.items():
            for dep in deps:
                dep_name = dep if isinstance(dep, str) else dep
                downstream_count[dep_name] = downstream_count.get(dep_name, 0) + 1

        spofs = []
        for comp, count in sorted(downstream_count.items(), key=lambda x: -x[1]):
            if count >= 2:
                spofs.append(SinglePointOfFailure(
                    component=comp,
                    reason=f"Shared dependency used by {count} components",
                    downstream_count=count,
                ))
        return spofs

    def _find_coupling_risks(
        self, adjacency: dict[str, list[str]],
        components: list[ComponentEntry],
    ) -> list[CouplingRisk]:
        risks: list[CouplingRisk] = []

        # Check for services that depend on each other (potential cycles)
        dep_pairs = set()
        for node, deps in adjacency.items():
            for dep in deps:
                dep_name = dep if isinstance(dep, str) else dep
                if dep_name in adjacency and node in adjacency.get(dep_name, []):
                    dep_pairs.add(tuple(sorted([node, dep_name])))

        for a, b in dep_pairs:
            risks.append(CouplingRisk(
                components=[a, b],
                risk_type="bidirectional_dependency",
                description=f"{a} and {b} depend on each other",
            ))

        return risks

    def _generate_risk_flags(
        self, critical_paths: list[CriticalPath],
        spofs: list[SinglePointOfFailure],
        adjacency: dict[str, list[str]],
    ) -> list[str]:
        flags = []

        for cp in critical_paths:
            if cp.length > 3:
                flags.append(f"Deep dependency chain: {' -> '.join(cp.path[:4])}... ({cp.length} hops)")

        for spof in spofs:
            flags.append(f"SPOF: {spof.component} ({spof.downstream_count} dependents)")

        for node, deps in adjacency.items():
            dep_names = [d if isinstance(d, str) else d for d in deps]
            if len(dep_names) >= 4:
                flags.append(f"Shared dependency bottleneck: {node} depends on {len(dep_names)} sources")

        return flags

    async def get_latest(self) -> SystemSafetyReport | None:
        return self._latest


system_safety_audit_service = SystemSafetyAuditService()
