from decimal import Decimal

import httpx

from app.core.logging import logger

JUPITER_QUOTE_API = "https://quote-api.jup.ag/v6"


class JupiterPriceFeed:
    """READ-ONLY price feed for Jupiter quotes.

    Fetches quotes from Jupiter's REST API.
    NO swap execution, NO transaction building, NO signing.
    """

    def __init__(self, base_url: str = JUPITER_QUOTE_API, timeout: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 100,
    ) -> dict | None:
        url = f"{self._base_url}/quote"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": str(slippage_bps),
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            logger.warning("jupiter_price_feed_timeout", input_mint=input_mint, output_mint=output_mint)
        except httpx.HTTPStatusError as e:
            logger.warning("jupiter_price_feed_http_error", status=e.response.status_code, input_mint=input_mint)
        except Exception as e:
            logger.warning("jupiter_price_feed_error", error=str(e), input_mint=input_mint)
        return None

    @staticmethod
    def parse_quote_response(data: dict) -> dict:
        out_amount = int(data.get("outAmount", 0))
        price_impact = float(data.get("priceImpactPct", 0))
        route_plan = data.get("routePlan", [])
        return {
            "out_amount": Decimal(str(out_amount)) / Decimal("1000000"),
            "price_impact_pct": price_impact,
            "route_count": len(route_plan),
            "context_slot": data.get("contextSlot"),
        }
