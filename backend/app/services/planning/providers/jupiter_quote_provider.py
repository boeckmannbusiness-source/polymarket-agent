import time
from datetime import datetime, timezone
from decimal import Decimal

from app.domain.execution.instrument import Instrument
from app.domain.planning.quote import Quote
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.services.planning.providers.base_quote_provider import BaseQuoteProvider
from app.services.planning.providers.jupiter_price_feed import JupiterPriceFeed
from app.services.market_data.price_oracle import PriceOracle


SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


class JupiterQuoteProvider(BaseQuoteProvider):
    """Real quote provider using Jupiter READ-ONLY price feed.

    Falls back to PriceOracle cache when Jupiter API is unavailable.
    """

    def __init__(
        self,
        price_feed: JupiterPriceFeed | None = None,
        oracle: PriceOracle | None = None,
    ):
        self._price_feed = price_feed or JupiterPriceFeed()
        self._oracle = oracle or PriceOracle()

    async def get_quote(
        self,
        instrument: Instrument,
        amount_in: Decimal,
        side: str,
        constraints: ExecutionConstraints | None = None,
    ) -> Quote:
        start = time.time()
        slippage = constraints.max_slippage_bps if constraints else 100

        quote = await self._try_fetch_quote(instrument, amount_in, slippage)

        elapsed_ms = (time.time() - start) * 1000

        if quote is not None:
            return quote

        return await self._fallback_quote(instrument, amount_in, slippage, elapsed_ms)

    async def _try_fetch_quote(
        self,
        instrument: Instrument,
        amount_in: Decimal,
        slippage_bps: int,
    ) -> Quote | None:
        input_mint = self._resolve_mint(instrument.asset_identifier)
        output_mint = self._resolve_mint(instrument.quote_asset)
        if not input_mint or not output_mint:
            return None

        amount_lamports = int(amount_in * Decimal("1000000"))
        raw = await self._price_feed.get_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount_lamports,
            slippage_bps=slippage_bps,
        )
        if raw is None:
            return None

        parsed = JupiterPriceFeed.parse_quote_response(raw)
        price = parsed["out_amount"] / amount_in if amount_in else Decimal("0")
        ts = datetime.now(timezone.utc)

        self._oracle.set_price(instrument.symbol, instrument.venue, float(price))

        return Quote(
            instrument=instrument,
            amount_in=amount_in,
            expected_amount_out=parsed["out_amount"],
            estimated_price=price,
            slippage_bps=slippage_bps,
            source="jupiter",
            timestamp=ts,
            source_latency_ms=None,
            price_impact_estimate=parsed["price_impact_pct"],
            liquidity_depth=parsed["out_amount"],
            venue_hint="jupiter",
        )

    async def _fallback_quote(
        self,
        instrument: Instrument,
        amount_in: Decimal,
        slippage_bps: int,
        caller_latency_ms: float,
    ) -> Quote:
        cached = self._oracle.get_price(instrument.symbol, instrument.venue)
        ts = datetime.now(timezone.utc)

        if cached is not None:
            price = Decimal(str(cached))
            return Quote(
                instrument=instrument,
                amount_in=amount_in,
                expected_amount_out=amount_in,
                estimated_price=price,
                slippage_bps=slippage_bps,
                source="oracle_cache",
                timestamp=ts,
                source_latency_ms=caller_latency_ms,
                venue_hint=instrument.venue,
            )

        return Quote(
            instrument=instrument,
            amount_in=amount_in,
            expected_amount_out=amount_in,
            estimated_price=Decimal("0"),
            slippage_bps=slippage_bps,
            source="simulated",
            timestamp=ts,
            source_latency_ms=caller_latency_ms,
            venue_hint=instrument.venue,
        )

    @staticmethod
    def _resolve_mint(asset: str) -> str | None:
        lookup = {
            "SOL": SOL_MINT,
            "USDC": USDC_MINT,
            "so11111111111111111111111111111111111111112": SOL_MINT,
            "epjfwdd5aufqssqem2qn1xzybapc8g4weggkzwytdt1v": USDC_MINT,
        }
        key = asset.lower() if asset else ""
        return lookup.get(key) or lookup.get(asset)
