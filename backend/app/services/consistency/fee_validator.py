from decimal import Decimal

from app.domain.execution import ExecutionResult
from app.services.consistency.consistency_report import ConsistencyCheck


class FeeValidator:
    def validate(self, result: ExecutionResult) -> list[ConsistencyCheck]:
        checks: list[ConsistencyCheck] = []
        checks.append(self._check_fee_aggregation(result))
        return checks

    @staticmethod
    def _check_fee_aggregation(result: ExecutionResult) -> ConsistencyCheck:
        if not result.fills:
            return ConsistencyCheck(
                name="fee_delta_check",
                passed=True,
                expected="0",
                actual="no fills",
            )
        fee_sum_from_fills = sum((f.fee or Decimal("0")) for f in result.fills)
        total_fees = result.fees or Decimal("0")
        diff = abs(fee_sum_from_fills - total_fees)
        passed = diff <= Decimal("0.001")
        return ConsistencyCheck(
            name="fee_delta_check",
            passed=passed,
            expected=str(total_fees),
            actual=str(fee_sum_from_fills),
            tolerance="0.001",
        )
