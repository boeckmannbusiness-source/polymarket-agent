from datetime import datetime, timezone
from decimal import Decimal

from app.domain.execution.instrument import Instrument
from app.domain.planning.quote import Quote


class PolymarketQuoteTranslator:
    """Legacy compatibility: converts Polymarket order assumptions to Quote.

    This is the ONLY component that may reference Polymarket-specific concepts
    (outcome, probability, clob). It serves as the bridge between legacy
    Polymarket data and the venue-agnostic planning layer.
    """

    @staticmethod
    def to_quote(
        instrument: Instrument,
        amount_in: Decimal,
        side: str,
        outcome: str | None = None,
        probability: float | None = None,
        slippage_bps: int = 100,
    ) -> Quote:
        expected_price = Decimal(str(probability)) if probability is not None else Decimal("0")
        return Quote(
            instrument=instrument,
            amount_in=amount_in,
            expected_amount_out=amount_in,
            estimated_price=expected_price,
            slippage_bps=slippage_bps,
            source="polymarket_legacy",
            timestamp=datetime.now(timezone.utc),
            venue_hint="polymarket",
        )
