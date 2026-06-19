from abc import ABC
from decimal import Decimal

from app.domain.execution.instrument import Instrument
from app.domain.planning.quote import Quote
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.services.planning.quote_provider import QuoteProvider


class BaseQuoteProvider(QuoteProvider, ABC):
    """Extended base for quote providers with common helpers.

    Subclasses must implement get_quote().
    """

    async def get_quote(
        self,
        instrument: Instrument,
        amount_in: Decimal,
        side: str,
        constraints: ExecutionConstraints | None = None,
    ) -> Quote:
        ...
