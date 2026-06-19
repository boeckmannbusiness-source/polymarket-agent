from abc import ABC, abstractmethod
from decimal import Decimal

from app.domain.execution.instrument import Instrument
from app.domain.planning.quote import Quote
from app.domain.planning.execution_constraints import ExecutionConstraints


class QuoteProvider(ABC):
    @abstractmethod
    async def get_quote(
        self,
        instrument: Instrument,
        amount_in: Decimal,
        side: str,
        constraints: ExecutionConstraints | None = None,
    ) -> Quote:
        ...
