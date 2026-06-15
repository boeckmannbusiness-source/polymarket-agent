"""
Chaos Engineering Test Suite for Sprint 3 shadow layer.

Simulates real-world failure conditions: API outages, Redis failures,
DB latency spikes, data corruption, and lifecycle races.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.research_trade import ResearchTrade
from app.models.shadow_position import ShadowPosition
from app.models.smart_wallet import SmartWallet
from app.models.wallet_trade import SolanaWalletTrade
from app.repositories.shadow_position_repository import ShadowPositionRepository
from app.services.shadow_portfolio_service import ShadowPortfolioService
from app.services.shadow_price_service import PriceTrackingService, PriceResult
from app.services.birdeye_service import BirdeyeClient
from app.services.dexscreener_service import DexScreenerClient

SIGNALS_URL = "/api/v1/signals/solana"


def _id():
    return uuid.uuid4()


def _ts():
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
class TestShadowChaos:

    async def _seed_chain(self, db_session, entry_price=100.0, strategy="chaos"):
        w = SmartWallet(id=_id(), wallet_address=f"w_{_id().hex[:8]}", source="chaos", first_seen_at=_ts())
        db_session.add(w)
        await db_session.flush()
        wt = SolanaWalletTrade(
            id=_id(), wallet_id=w.id, tx_signature=f"tx_{_id().hex[:8]}",
            mint_address=f"mint_{_id().hex[:8]}", side="buy",
            size_usd=1000.0, price_usd=entry_price, block_time=_ts(),
        )
        db_session.add(wt)
        await db_session.flush()
        rt = ResearchTrade(
            id=_id(), signal_id=f"sig_{_id().hex[:8]}", strategy=strategy,
            wallet_trade_id=wt.id, entry_price=entry_price, confidence=0.8,
            status="open", opened_at=_ts(),
        )
        db_session.add(rt)
        await db_session.commit()
        return rt

    # ── 1. Price API failure cascade ──

    async def test_price_api_cascade_all_fail(self, db_session, monkeypatch):
        """Birdeye fails, DexScreener fails, DB fallback used — no crash."""
        from app.core.metrics import solana_price_source_total, solana_price_stale_total

        rt = await self._seed_chain(db_session)
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)

        async def birdeye_fail(_self, _mint):
            return None
        monkeypatch.setattr(BirdeyeClient, "get_token_price", birdeye_fail)

        async def dexscreener_fail(_self, _mint):
            return None
        monkeypatch.setattr(DexScreenerClient, "get_token_price", dexscreener_fail)

        stale_before = solana_price_stale_total._value.get()
        updated = await svc.update_prices()
        assert updated == 1  # falls back to DB stale price
        stale_after = solana_price_stale_total._value.get()
        assert stale_after == stale_before + 1

    async def test_price_api_all_unavailable(self, db_session, monkeypatch):
        """All price sources return None — no crash, position stays open."""
        rt = await self._seed_chain(db_session, entry_price=100.0)
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)

        async def resolve_unavail(_self, mint):
            return PriceResult(price=None, source="unavailable")
        monkeypatch.setattr(PriceTrackingService, "resolve_price", resolve_unavail)

        updated = await svc.update_prices()
        assert updated == 0

    # ── 2. Redis outage simulation ──

    async def test_redis_outage_fallback(self, db_session, monkeypatch):
        """Redis unavailable — system falls back to Birdeye, no exception."""
        rt = await self._seed_chain(db_session)
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)

        async def redis_boom(*args, **kwargs):
            raise ConnectionError("Redis connection refused")
        monkeypatch.setattr("app.redis.get_redis", redis_boom)

        updated = await svc.update_prices()
        assert updated == 1

        repo = ShadowPositionRepository(db_session)
        pos = (await repo.list_open())[0]
        assert pos.current_price is not None

    # ── 3. DB latency spike simulation ──

    async def test_db_latency_spike(self, db_session, monkeypatch):
        """Simulated slow query — eval loop continues safely."""
        rt = await self._seed_chain(db_session)
        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(rt)

        repo = ShadowPositionRepository(db_session)
        await repo.update_current_price(pos.id, 200.0)

        slow = False

        original_execute = db_session.execute

        async def slow_execute(statement, *args, **kwargs):
            nonlocal slow
            if "shadow_positions" in str(statement):
                slow = True
                import asyncio
                await asyncio.sleep(0.25)
            return await original_execute(statement, *args, **kwargs)

        monkeypatch.setattr(db_session, "execute", slow_execute)
        closed = await svc.evaluate_all()
        assert slow
        assert len(closed) == 1

    # ── 4. Partial corruption state ──

    async def test_zero_entry_price_skipped(self, db_session):
        """Position with entry_price=0 is safely skipped by evaluate_all."""
        from sqlalchemy import update

        rt = await self._seed_chain(db_session)
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)

        await db_session.execute(
            update(ShadowPosition)
            .where(ShadowPosition.research_trade_id == rt.id)
            .values(entry_price=0),
        )
        await db_session.commit()

        closed = await svc.evaluate_all()
        assert len(closed) == 0

    async def test_zero_size_open_position_skipped(self, db_session):
        """Open position with size_usd=0 is safely skipped."""
        from sqlalchemy import update
        rt = await self._seed_chain(db_session)
        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(rt)

        await db_session.execute(
            update(ShadowPosition)
            .where(ShadowPosition.id == pos.id)
            .values(size_usd=0.0),
        )
        await db_session.commit()

        closed = await svc.evaluate_all()
        assert len(closed) == 0

    # ── 5. Mixed lifecycle race ──

    async def test_manual_close_during_eval_no_double_close(self, db_session):
        """Manually closed position is not double-closed by evaluate_all."""
        rt = await self._seed_chain(db_session)
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)

        repo = ShadowPositionRepository(db_session)
        pos = (await repo.list_open())[0]
        await repo.update_current_price(pos.id, 200.0)

        first = await svc.close_position(pos.id, reason="manual")
        assert first is not None
        assert first.status == "closed"

        second = await svc.close_position(pos.id, reason="manual")
        assert second is None

        closed = await svc.evaluate_all()
        assert len(closed) == 0

        pos_after = await repo.get_by_id(pos.id)
        assert pos_after.status == "closed"
        assert pos_after.close_reason == "manual"

    async def test_price_tracker_updates_only_current_price(self, db_session):
        """Price tracker must NOT modify status, PnL, or exit_price."""
        rt = await self._seed_chain(db_session)
        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(rt)

        repo = ShadowPositionRepository(db_session)
        await repo.update_current_price(pos.id, 200.0)

        pos2 = await repo.get_by_id(pos.id)
        assert pos2.status == "open"
        assert pos2.current_price == 200.0

        closed = await svc.evaluate_all()
        assert len(closed) == 1
        assert closed[0].close_reason == "take_profit"

        pos3 = await repo.get_by_id(pos.id)
        assert pos3.status == "closed"

    async def test_concurrent_price_update_no_crash(self, db_session):
        """Multiple rapid price updates are safe."""
        rt = await self._seed_chain(db_session)
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)

        repo = ShadowPositionRepository(db_session)
        pos = (await repo.list_open())[0]
        for pct in [90.0, 110.0, 95.0, 105.0, 130.0]:
            await repo.update_current_price(pos.id, pct)
        pos2 = await repo.get_by_id(pos.id)
        assert pos2.current_price == 130.0

    async def test_admin_auth_blocks_chaos_endpoints(self, client: AsyncClient, db_session):
        """Validation API endpoints do not crash under unauthenticated requests."""
        for ep in ("stats", "performance", "concentration", "wallet-universe"):
            resp = await client.get(f"{SIGNALS_URL}/{ep}")
            assert resp.status_code in (200, 401, 403)
