from decimal import Decimal

from app.domain.execution.instrument import Instrument
from app.domain.planning.quote import Quote
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.services.market_data.price_oracle import PriceOracle
from app.services.planning.quote_provider import QuoteProvider


class MarketDataService:
    """Unified market data access layer.

    Combines live quote providers with price oracle caching.
    """

    def __init__(
        self,
        quote_provider: QuoteProvider,
        oracle: PriceOracle | None = None,
    ):
        self._quote_provider = quote_provider
        self._oracle = oracle or PriceOracle()

    async def get_quote(
        self,
        instrument: Instrument,
        amount_in: Decimal,
        side: str = "buy",
        constraints: ExecutionConstraints | None = None,
    ) -> Quote:
        return await self._quote_provider.get_quote(instrument, amount_in, side, constraints)

    def get_cached_price(self, symbol: str, venue: str) -> float | None:
        return self._oracle.get_price(symbol, venue)
