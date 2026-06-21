import httpx
from decimal import Decimal
from typing import Optional, Dict, Any
from app.domain.planning.quote import Quote
from app.domain.execution.instrument import Instrument
from app.core.logging import logger

class JupiterQuoteClient:
    """Jupiter API Client for read-only quotes."""

    BASE_URL = "https://quote-api.jup.ag/v6"

    async def get_quote(
        self,
        instrument: Instrument,
        input_mint: str,
        output_mint: str,
        amount: Decimal,
        slippage_bps: int = 100,
        **kwargs
    ) -> Optional[Quote]:
        """Fetch a quote from Jupiter API.

        Args:
            instrument: The instrument being quoted.
            input_mint: The mint address of the input token.
            output_mint: The mint address of the output token.
            amount: The amount of input token in Decimal.
            slippage_bps: Slippage tolerance in basis points.
        """
        # Convert amount to lamports (heuristic: 10^9 for SOL/USDC for quote API)
        amount_lamports = int(amount * Decimal("1000000000"))

        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount_lamports,
            "slippageBps": slippage_bps,
            "onlyDirectRoutes": "false"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.BASE_URL}/quote", params=params, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    out_amount = Decimal(data["outAmount"]) / Decimal("1000000000")
                    price = out_amount / amount if amount else Decimal("0")

                    from datetime import datetime, timezone
                    return Quote(
                        instrument=instrument,
                        amount_in=amount,
                        expected_amount_out=out_amount,
                        estimated_price=price,
                        slippage_bps=slippage_bps,
                        source="jupiter",
                        timestamp=datetime.now(timezone.utc),
                        price_impact_estimate=float(data.get("priceImpactPct", 0)),
                        venue_hint="jupiter"
                    )
                else:
                    logger.error("jupiter_quote_error", status=response.status_code, body=response.text)
                    return None
        except Exception as e:
            logger.error("jupiter_quote_exception", error=str(e))
            return None
