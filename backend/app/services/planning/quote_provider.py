from abc import ABC, abstractmethod
from decimal import Decimal

from app.domain.execution.instrument import Instrument
from app.domain.planning.quote import Quote
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.domain.assets import AssetResolution


class QuoteProvider(ABC):
    @abstractmethod
    async def get_quote(
        self,
        instrument: Instrument,
        amount_in: Decimal,
        side: str,
        constraints: ExecutionConstraints | None = None,
        asset_resolution: AssetResolution | None = None,
        quote_asset_resolution: AssetResolution | None = None,
        **kwargs,
    ) -> Quote:
        ...
