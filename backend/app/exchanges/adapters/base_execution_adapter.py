from abc import ABC, abstractmethod

from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.execution import ExecutionResult


class BaseExecutionAdapter(ABC):
    """New execution adapter interface consuming TransactionPlan.

    This supersedes the old BaseExchangeAdapter.submit_order(intent) pattern.
    """

    @abstractmethod
    async def execute(self, plan: TransactionPlan) -> ExecutionResult:
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        ...

    @abstractmethod
    async def get_supported_assets(self) -> list[str]:
        ...
