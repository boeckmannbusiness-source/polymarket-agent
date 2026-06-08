from datetime import datetime, timezone

from app.schemas.audit_v2 import FeedbackCycleReport, FeedbackCycle


class FeedbackCycleCheckService:
    def __init__(self):
        self._latest: FeedbackCycleReport | None = None

    async def check(self) -> FeedbackCycleReport:
        graph = self._build_dependency_graph()
        cycles = self._detect_all_cycles(graph)
        cycle_entries = self._classify_cycles(cycles)
        overall_risk = self._compute_overall_risk(cycle_entries)
        risk_flags = self._generate_risk_flags(cycle_entries)

        report = FeedbackCycleReport(
            cycles=cycle_entries,
            overall_risk_level=overall_risk,
            risk_flags=risk_flags,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._latest = report
        return report

    def _build_dependency_graph(self) -> dict[str, list[str]]:
        return {
            "autonomous_portfolio_review": ["portfolio_intelligence_service",
                "regime_allocation_service", "stress_testing_service",
                "resilience_service", "investment_committee_service"],
            "portfolio_intelligence_service": ["strategy_performance", "regime_data"],
            "regime_allocation_service": ["regime_data"],
            "stress_testing_service": ["strategy_health"],
            "resilience_service": ["strategy_correlations"],
            "investment_committee_service": ["portfolio_intelligence_service",
                "resilience_service", "regime_allocation_service"],
            "autonomous_optimization_pipeline": ["regime_expected_return_model",
                "risk_model_service", "portfolio_optimization_engine",
                "monte_carlo_simulation_service", "allocation_learning_service"],
            "regime_expected_return_model": ["regime_data"],
            "risk_model_service": ["market_correlations", "regime_data"],
            "portfolio_optimization_engine": ["regime_expected_return_model",
                "risk_model_service"],
            "monte_carlo_simulation_service": ["risk_model_service"],
            "allocation_learning_service": ["portfolio_optimization_engine",
                "strategy_performance"],
            "autonomous_control_pipeline": ["stability_controller",
                "feedback_dampening_service", "portfolio_drift_detector",
                "regime_transition_controller"],
            "stability_controller": ["portfolio_optimization_engine"],
            "feedback_dampening_service": ["allocation_learning_service"],
            "portfolio_drift_detector": ["stability_controller",
                "portfolio_optimization_engine"],
            "regime_transition_controller": ["regime_data"],
            "control_plane": ["autonomous_control_pipeline"],
        }

    def _detect_all_cycles(
        self, graph: dict[str, list[str]]
    ) -> list[list[str]]:
        cycles: list[list[str]] = []
        all_nodes = list(graph.keys())
        all_deps: set[str] = set()
        for deps in graph.values():
            for d in deps:
                all_deps.add(d)
        for node in all_deps:
            if node not in graph:
                graph[node] = []

        def dfs(node: str, visited: set[str], stack: list[str], path: set[str]):
            visited.add(node)
            path.add(node)
            stack.append(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, visited, stack, path)
                elif neighbor in path:
                    # Found a cycle — extract it
                    idx = stack.index(neighbor)
                    cycle = stack[idx:] + [neighbor]
                    # Normalize to avoid duplicates
                    min_idx = cycle.index(min(cycle))
                    normalized = cycle[min_idx:] + cycle[:min_idx]
                    if not any(self._same_cycle(normalized, c) for c in cycles):
                        cycles.append(normalized)
            stack.pop()
            path.discard(node)

        for node in graph:
            if node not in set().union(*[{s} for s in [
                k for k in graph.keys()
            ]]):
                pass

        visited: set[str] = set()
        for node in graph:
            if node not in visited:
                dfs(node, set(), [], set())

        return cycles

    def _same_cycle(self, a: list[str], b: list[str]) -> bool:
        if len(a) != len(b):
            return False
        doubled = a + a
        for i in range(len(a)):
            if doubled[i:i + len(b)] == b:
                return True
        return False

    def _classify_cycles(self, cycles: list[list[str]]) -> list[FeedbackCycle]:
        result: list[FeedbackCycle] = []
        for cycle in cycles:
            length = len(cycle) - 1  # -1 because last repeats first
            risk_level = self._determine_risk_level(cycle)
            result.append(FeedbackCycle(
                cycle=list(cycle),
                cycle_length=length,
                risk_level=risk_level,
            ))
        return result

    def _determine_risk_level(self, cycle: list[str]) -> str:
        control_keywords = ["stability_controller", "feedback_dampening",
                           "control_plane", "autonomous_control_pipeline"]
        optimization_keywords = ["portfolio_optimization_engine",
                                "allocation_learning_service",
                                "autonomous_optimization_pipeline"]

        has_control = any(k in " ".join(cycle) for k in control_keywords)
        has_optimization = any(k in " ".join(cycle) for k in optimization_keywords)

        if len(cycle) - 1 <= 2 and (has_control or has_optimization):
            return "HIGH"
        elif has_control or has_optimization:
            return "HIGH"
        elif len(cycle) - 1 <= 2:
            return "MEDIUM"
        return "MEDIUM"

    def _compute_overall_risk(self, cycles: list[FeedbackCycle]) -> str:
        if not cycles:
            return "LOW"
        if any(c.risk_level == "HIGH" for c in cycles):
            return "HIGH"
        if any(c.risk_level == "MEDIUM" for c in cycles):
            return "MEDIUM"
        return "LOW"

    def _generate_risk_flags(self, cycles: list[FeedbackCycle]) -> list[str]:
        flags = []
        for c in cycles:
            if c.risk_level == "HIGH":
                flags.append(
                    f"Direct cycle: {' -> '.join(c.cycle)}"
                )
            elif c.risk_level == "MEDIUM":
                flags.append(
                    f"Indirect cycle: {' -> '.join(c.cycle)}"
                )
        if not cycles:
            flags.append("No cycles detected — dependency graph is acyclic")
        return flags

    async def get_latest(self) -> FeedbackCycleReport | None:
        return self._latest


feedback_cycle_check_service = FeedbackCycleCheckService()
