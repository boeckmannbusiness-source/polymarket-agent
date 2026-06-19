from abc import ABC, abstractmethod

from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.execution_constraints import ExecutionConstraints


class TransactionBuilder(ABC):
    @abstractmethod
    async def build(
        self,
        quote: Quote,
        route: Route,
        constraints: ExecutionConstraints | None = None,
    ) -> TransactionPlan:
        ...
