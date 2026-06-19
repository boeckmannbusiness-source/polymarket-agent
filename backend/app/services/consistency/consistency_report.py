from datetime import datetime
from pydantic import BaseModel

from app.domain.execution import ExecutionResult
from app.domain.portfolio import PortfolioSnapshot, PositionProjection, ExecutionFeedback


class ConsistencyCheck(BaseModel):
    name: str
    passed: bool
    expected: str | None = None
    actual: str | None = None
    tolerance: str | None = None


class ConsistencyReport(BaseModel):
    timestamp: datetime
    execution_id: str
    checks: list[ConsistencyCheck]
    all_passed: bool

    @property
    def failed_checks(self) -> list[ConsistencyCheck]:
        return [c for c in self.checks if not c.passed]


class ValidatedExecutionBundle(BaseModel):
    execution_result: ExecutionResult
    snapshot: PortfolioSnapshot
    projections: list[PositionProjection]
    feedback: ExecutionFeedback
    report: ConsistencyReport
