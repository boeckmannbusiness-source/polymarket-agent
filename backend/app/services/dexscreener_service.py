import httpx


class DexScreenerClient:
    BASE_URL = "https://api.dexscreener.com/latest/dex/tokens"

    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    async def get_token_price(self, mint_address: str) -> float | None:
        url = f"{self.BASE_URL}/{mint_address}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                body = resp.json()
                pairs = body.get("pairs", []) or []
                best = None
                for pair in pairs:
                    if pair.get("chainId") != "solana":
                        continue
                    price = pair.get("priceUsd")
                    if price is None:
                        continue
                    liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                    if best is None or liq > best["liquidity"]:
                        best = {"price": float(price), "liquidity": liq}
                return best["price"] if best else None
            except (httpx.HTTPError, httpx.RequestError, ValueError, TypeError, KeyError):
                return None
