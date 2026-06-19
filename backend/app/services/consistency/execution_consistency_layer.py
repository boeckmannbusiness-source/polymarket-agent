from datetime import datetime, timezone

from app.domain.execution import ExecutionResult
from app.domain.portfolio import PortfolioSnapshot, PositionProjection, ExecutionFeedback
from app.services.consistency.consistency_report import ConsistencyCheck, ConsistencyReport, ValidatedExecutionBundle
from app.services.consistency.delta_validator import DeltaValidator
from app.services.consistency.fee_validator import FeeValidator
from app.services.consistency.route_validator import RouteValidator


class ExecutionConsistencyLayer:
    def __init__(
        self,
        delta_validator: DeltaValidator | None = None,
        fee_validator: FeeValidator | None = None,
        route_validator: RouteValidator | None = None,
    ):
        self._delta_validator = delta_validator or DeltaValidator()
        self._fee_validator = fee_validator or FeeValidator()
        self._route_validator = route_validator or RouteValidator()

    def validate(
        self,
        result: ExecutionResult,
        snapshot: PortfolioSnapshot,
        projections: list[PositionProjection],
        feedback: ExecutionFeedback,
    ) -> ValidatedExecutionBundle:
        checks: list[ConsistencyCheck] = []
        checks.extend(self._delta_validator.validate(result, snapshot, feedback))
        checks.extend(self._fee_validator.validate(result))
        checks.extend(self._route_validator.validate(result))

        report = ConsistencyReport(
            timestamp=datetime.now(timezone.utc),
            execution_id=result.execution_id,
            checks=checks,
            all_passed=all(c.passed for c in checks),
        )

        return ValidatedExecutionBundle(
            execution_result=result,
            snapshot=snapshot,
            projections=projections,
            feedback=feedback,
            report=report,
        )
