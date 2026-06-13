import time
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


class MemoryCache:
    def __init__(self, ttl_seconds: int = 60, maxsize: int = 500):
        self._data: dict[str, tuple[float, float]] = {}
        self.ttl = ttl_seconds
        self.maxsize = maxsize

    def get(self, key: str) -> float | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, cached_at = entry
        if time.monotonic() - cached_at >= self.ttl:
            del self._data[key]
            return None
        return value

    def set(self, key: str, value: float) -> None:
        self._data[key] = (value, time.monotonic())
        if len(self._data) > self.maxsize:
            oldest = min(self._data.items(), key=lambda kv: kv[1][1])
            del self._data[oldest[0]]


class BirdeyeClient:
    BASE_URL = "https://public-api.birdeye.so"

    def __init__(self, api_key: str, timeout: int = 10):
        self.api_key = api_key
        self.timeout = timeout

    async def get_token_price(self, mint_address: str) -> float | None:
        if not self.api_key:
            return None

        url = f"{self.BASE_URL}/public/price?address={mint_address}"
        headers = {"x-api-key": self.api_key}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 429:
                    return None
                resp.raise_for_status()
                body = resp.json()
                if not body.get("success"):
                    return None
                value = body.get("data", {}).get("value")
                return float(value) if value is not None else None
            except (httpx.HTTPError, httpx.RequestError, ValueError, TypeError):
                return None


class BirdeyeEnrichmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = BirdeyeClient(api_key=settings.BIRDEYE_API_KEY)
        self.cache = MemoryCache(ttl_seconds=60, maxsize=500)
        from app.repositories.wallet_trade_repository import WalletTradeRepository
        self.trade_repo = WalletTradeRepository(db)

    async def enrich_trade(self, trade_id: uuid.UUID, token_amount: float | None = None) -> bool:
        trade = await self.trade_repo.get_by_id(trade_id)
        if not trade:
            return False

        if trade.price_usd is not None and trade.price_usd > 0:
            return True

        price = await self._get_price(trade.mint_address)
        if price is None:
            return False

        trade.price_usd = round(price, 8)
        if token_amount is not None and token_amount > 0:
            trade.size_usd = round(token_amount * price, 8)

        await self.db.commit()
        await self.db.refresh(trade)
        return True

    async def enrich_batch(self, trade_ids: list[uuid.UUID]) -> int:
        count = 0
        for tid in trade_ids:
            if await self.enrich_trade(tid):
                count += 1
        return count

    async def _get_price(self, mint_address: str) -> float | None:
        cached = self.cache.get(mint_address)
        if cached is not None:
            return cached

        price = await self.client.get_token_price(mint_address)
        if price is not None:
            self.cache.set(mint_address, price)
            return price

        return None
