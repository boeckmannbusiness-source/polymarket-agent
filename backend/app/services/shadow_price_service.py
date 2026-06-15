import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.wallet_trade import SolanaWalletTrade
from app.services.birdeye_service import BirdeyeClient
from app.services.dexscreener_service import DexScreenerClient


class PriceResult:
    def __init__(self, price: Decimal | None, source: str):
        self.price = price
        self.source = source


class PriceTrackingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.birdeye = BirdeyeClient(api_key=settings.BIRDEYE_API_KEY)
        self.dexscreener = DexScreenerClient()

    async def get_current_price(self, mint_address: str) -> float | None:
        result = await self.db.execute(
            select(SolanaWalletTrade.price_usd)
            .where(SolanaWalletTrade.mint_address == mint_address)
            .where(SolanaWalletTrade.price_usd.isnot(None))
            .where(SolanaWalletTrade.price_usd > 0)
            .order_by(desc(SolanaWalletTrade.block_time))
            .limit(1),
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return float(row)
        return None

    async def cache_price_redis(self, mint_address: str, price: float) -> None:
        try:
            from app.redis import get_redis
            r = await get_redis()
            await r.setex(
                f"solana:price:{mint_address}",
                settings.SOLANA_SHADOW_PRICE_TTL,
                json.dumps({"price": str(price), "updated_at": datetime.now(timezone.utc).isoformat()}),
            )
        except Exception:
            pass

    async def get_cached_price_redis(self, mint_address: str) -> float | None:
        try:
            from app.redis import get_redis
            r = await get_redis()
            raw = await r.get(f"solana:price:{mint_address}")
            if raw:
                data = json.loads(raw)
                return float(data["price"])
        except Exception:
            pass
        return None

    async def resolve_price(self, mint_address: str) -> PriceResult:
        from app.core.metrics import (
            solana_price_source_total,
            solana_price_stale_total,
            solana_price_fetch_seconds,
            solana_price_update_total,
        )

        t0 = time.monotonic()

        cached = await self.get_cached_price_redis(mint_address)
        if cached is not None:
            dur = time.monotonic() - t0
            solana_price_source_total.labels(source="redis").inc()
            solana_price_fetch_seconds.observe(dur)
            return PriceResult(price=Decimal(str(cached)), source="redis")

        birdeye_price = await self.birdeye.get_token_price(mint_address)
        if birdeye_price is not None:
            await self.cache_price_redis(mint_address, birdeye_price)
            dur = time.monotonic() - t0
            solana_price_source_total.labels(source="birdeye").inc()
            solana_price_fetch_seconds.observe(dur)
            solana_price_update_total.inc()
            return PriceResult(price=Decimal(str(birdeye_price)), source="birdeye")

        dex_price = await self.dexscreener.get_token_price(mint_address)
        if dex_price is not None:
            await self.cache_price_redis(mint_address, dex_price)
            dur = time.monotonic() - t0
            solana_price_source_total.labels(source="dexscreener").inc()
            solana_price_fetch_seconds.observe(dur)
            solana_price_update_total.inc()
            return PriceResult(price=Decimal(str(dex_price)), source="dexscreener")

        db_price = await self.get_current_price(mint_address)
        if db_price is not None:
            dur = time.monotonic() - t0
            solana_price_source_total.labels(source="stale").inc()
            solana_price_fetch_seconds.observe(dur)
            solana_price_stale_total.inc()
            return PriceResult(price=Decimal(str(db_price)), source="stale")

        dur = time.monotonic() - t0
        solana_price_source_total.labels(source="unavailable").inc()
        solana_price_fetch_seconds.observe(dur)
        return PriceResult(price=None, source="unavailable")

    async def get_price_for_research_trade(self, research_trade_id: Any) -> float | None:
        from app.models.research_trade import ResearchTrade
        from sqlalchemy.orm import selectinload

        result = await self.db.execute(
            select(ResearchTrade)
            .options(selectinload(ResearchTrade.wallet_trade))
            .where(ResearchTrade.id == research_trade_id),
        )
        trade = result.scalar_one_or_none()
        if not trade or not trade.wallet_trade:
            return None
        result = await self.resolve_price(trade.wallet_trade.mint_address)
        return float(result.price) if result.price is not None else None
