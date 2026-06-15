import asyncio
from decimal import Decimal
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.shadow_price_service import PriceTrackingService, PriceResult


@pytest.mark.asyncio
class TestPriceTracker:
    async def test_redis_hit(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_redis_hit"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=150.0)) as mock_cache,
            patch.object(svc.birdeye, "get_token_price", AsyncMock()) as mock_birdeye,
            patch.object(svc.dexscreener, "get_token_price", AsyncMock()) as mock_dex,
            patch.object(svc, "get_current_price", AsyncMock()) as mock_db,
        ):
            result = await svc.resolve_price(mint)

        assert isinstance(result, PriceResult)
        assert result.price == Decimal("150.0")
        assert result.source == "redis"
        mock_cache.assert_awaited_once_with(mint)
        mock_birdeye.assert_not_called()
        mock_dex.assert_not_called()
        mock_db.assert_not_called()

    async def test_birdeye_success(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_birdeye_success"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=200.0)) as mock_birdeye,
            patch.object(svc.dexscreener, "get_token_price", AsyncMock()) as mock_dex,
            patch.object(svc, "get_current_price", AsyncMock()) as mock_db,
            patch.object(svc, "cache_price_redis", AsyncMock()) as mock_cache_set,
        ):
            result = await svc.resolve_price(mint)

        assert result.price == Decimal("200.0")
        assert result.source == "birdeye"
        mock_birdeye.assert_awaited_once_with(mint)
        mock_dex.assert_not_called()
        mock_db.assert_not_called()
        mock_cache_set.assert_awaited_once_with(mint, 200.0)

    async def test_dexscreener_fallback(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_dexscreener_fallback"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock(return_value=180.0)) as mock_dex,
            patch.object(svc, "get_current_price", AsyncMock()) as mock_db,
            patch.object(svc, "cache_price_redis", AsyncMock()) as mock_cache_set,
        ):
            result = await svc.resolve_price(mint)

        assert result.price == Decimal("180.0")
        assert result.source == "dexscreener"
        mock_dex.assert_awaited_once_with(mint)
        mock_db.assert_not_called()
        mock_cache_set.assert_awaited_once_with(mint, 180.0)

    async def test_stale_fallback(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_stale_fallback"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc, "get_current_price", AsyncMock(return_value=50.0)) as mock_db,
            patch.object(svc, "cache_price_redis", AsyncMock()) as mock_cache_set,
        ):
            result = await svc.resolve_price(mint)

        assert result.price == Decimal("50.0")
        assert result.source == "stale"
        mock_db.assert_awaited_once_with(mint)
        mock_cache_set.assert_not_called()

    async def test_unavailable(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_unavailable"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc, "get_current_price", AsyncMock(return_value=None)),
        ):
            result = await svc.resolve_price(mint)

        assert result.price is None
        assert result.source == "unavailable"

    async def test_redis_write_on_birdeye(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_redis_write"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=100.0)),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock()),
            patch.object(svc, "get_current_price", AsyncMock()),
            patch.object(svc, "cache_price_redis", AsyncMock()) as mock_cache_set,
        ):
            await svc.resolve_price(mint)

        mock_cache_set.assert_awaited_once_with(mint, 100.0)

    async def test_redis_write_on_dexscreener(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_redis_write_dex"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock(return_value=90.0)),
            patch.object(svc, "get_current_price", AsyncMock()),
            patch.object(svc, "cache_price_redis", AsyncMock()) as mock_cache_set,
        ):
            await svc.resolve_price(mint)

        mock_cache_set.assert_awaited_once_with(mint, 90.0)

    async def test_no_cache_write_on_stale(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_no_cache_stale"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc, "get_current_price", AsyncMock(return_value=50.0)),
            patch.object(svc, "cache_price_redis", AsyncMock()) as mock_cache_set,
        ):
            await svc.resolve_price(mint)

        mock_cache_set.assert_not_called()

    async def test_no_cache_write_on_unavailable(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_no_cache_unavail"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc, "get_current_price", AsyncMock(return_value=None)),
            patch.object(svc, "cache_price_redis", AsyncMock()) as mock_cache_set,
        ):
            await svc.resolve_price(mint)

        mock_cache_set.assert_not_called()

    async def test_cache_write_failure_ignored(self, db_session: AsyncSession):
        import app.redis as _redis_mod

        svc = PriceTrackingService(db_session)
        mint = "test_cache_fail_ignored"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=200.0)),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock()),
            patch.object(svc, "get_current_price", AsyncMock()),
            patch.object(_redis_mod, "get_redis", AsyncMock(side_effect=RuntimeError("redis down"))),
        ):
            result = await svc.resolve_price(mint)

        assert result.price == Decimal("200.0")
        assert result.source == "birdeye"

    async def test_timeout_fallback(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_timeout_fallback"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=None)) as mock_birdeye,
            patch.object(svc.dexscreener, "get_token_price", AsyncMock(return_value=120.0)) as mock_dex,
            patch.object(svc, "get_current_price", AsyncMock()),
        ):
            result = await svc.resolve_price(mint)

        assert result.source == "dexscreener"
        mock_birdeye.assert_awaited_once_with(mint)
        mock_dex.assert_awaited_once_with(mint)

    async def test_source_metric_increments(self, db_session: AsyncSession):
        from app.core.metrics import solana_price_source_total

        mint = "test_source_metric"

        svc = PriceTrackingService(db_session)
        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=300.0)),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock()),
            patch.object(svc, "get_current_price", AsyncMock()),
            patch.object(svc, "cache_price_redis", AsyncMock()),
        ):
            before = solana_price_source_total.labels(source="birdeye")._value.get()
            await svc.resolve_price(mint)
            after = solana_price_source_total.labels(source="birdeye")._value.get()

        assert after == before + 1

    async def test_concurrent_update(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_concurrent"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=300.0)),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock()),
            patch.object(svc, "get_current_price", AsyncMock()),
        ):
            r1, r2 = await asyncio.gather(
                svc.resolve_price(mint),
                svc.resolve_price(mint),
            )

        assert r1.price == r2.price == Decimal("300.0")
        assert r1.source == r2.source == "birdeye"

    async def test_price_result_type(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_pr_type"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=99.0)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock()),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock()),
            patch.object(svc, "get_current_price", AsyncMock()),
        ):
            result = await svc.resolve_price(mint)

        assert isinstance(result.price, Decimal)
        assert isinstance(result.source, str)

    async def test_price_result_unavailable_type(self, db_session: AsyncSession):
        svc = PriceTrackingService(db_session)
        mint = "test_pr_unavail"

        with (
            patch.object(svc, "get_cached_price_redis", AsyncMock(return_value=None)),
            patch.object(svc.birdeye, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc.dexscreener, "get_token_price", AsyncMock(return_value=None)),
            patch.object(svc, "get_current_price", AsyncMock(return_value=None)),
        ):
            result = await svc.resolve_price(mint)

        assert result.price is None
        assert result.source == "unavailable"

    async def test_update_current_price_only(self, db_session: AsyncSession):
        import uuid
        from datetime import datetime, timezone
        from app.models.shadow_position import ShadowPosition
        from app.repositories.shadow_position_repository import ShadowPositionRepository

        rt_id = uuid.uuid4()
        pos = ShadowPosition(
            id=uuid.uuid4(),
            research_trade_id=rt_id,
            strategy="s1",
            entry_price=100.0,
            size_usd=5000.0,
            current_price=100.0,
            gross_pnl_usd=55.0,
            net_pnl_usd=40.0,
            status="open",
            opened_at=datetime.now(timezone.utc),
        )
        db_session.add(pos)
        await db_session.commit()

        repo = ShadowPositionRepository(db_session)
        updated = await repo.update_current_price(pos.id, 110.0)

        assert updated is not None
        assert float(updated.current_price) == 110.0
        assert float(updated.gross_pnl_usd) == 55.0
        assert float(updated.net_pnl_usd) == 40.0
        assert updated.status == "open"
        assert updated.exit_price is None
        assert updated.close_reason is None
        assert updated.closed_at is None
