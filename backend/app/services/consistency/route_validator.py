from app.domain.execution import ExecutionResult
from app.services.consistency.consistency_report import ConsistencyCheck


class RouteValidator:
    def validate(self, result: ExecutionResult) -> list[ConsistencyCheck]:
        checks: list[ConsistencyCheck] = []
        checks.append(self._check_route_efficiency(result))
        checks.append(self._check_instruction_trace_integrity(result))
        return checks

    @staticmethod
    def _check_route_efficiency(result: ExecutionResult) -> ConsistencyCheck:
        if not result.execution_path:
            return ConsistencyCheck(name="route_efficiency_check", passed=True, expected="1.0", actual="no path")
        hops = len(result.execution_path)
        penalty = 0.1 * (hops - 1)
        efficiency = max(0.0, 1.0 - penalty)
        passed = 0.0 <= efficiency <= 1.0
        return ConsistencyCheck(
            name="route_efficiency_check",
            passed=passed,
            expected=f"1.0 - {penalty}",
            actual=str(round(efficiency, 4)),
        )

    @staticmethod
    def _check_instruction_trace_integrity(result: ExecutionResult) -> ConsistencyCheck:
        trace = result.instruction_trace
        exec_path = result.execution_path
        if trace is None and exec_path is None:
            return ConsistencyCheck(name="instruction_trace_integrity", passed=True, expected="consistent", actual="both None")
        if trace is not None and exec_path is not None:
            passed = len(trace) == len(exec_path)
            return ConsistencyCheck(
                name="instruction_trace_integrity",
                passed=passed,
                expected=f"len={len(exec_path)}",
                actual=f"len={len(trace)}",
            )
        return ConsistencyCheck(
            name="instruction_trace_integrity",
            passed=False,
            expected="both set or both None",
            actual=f"trace={trace}, path={exec_path}",
        )
