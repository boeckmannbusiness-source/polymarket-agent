import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.research_trade import ResearchTrade
from app.models.shadow_position import ShadowPosition
from app.models.smart_wallet import SmartWallet
from app.models.wallet_trade import SolanaWalletTrade
from app.repositories.shadow_position_repository import ShadowPositionRepository
from app.services.shadow_portfolio_service import ShadowPortfolioService
from app.services.shadow_price_service import PriceTrackingService, PriceResult

SIGNALS_URL = "/api/v1/signals/solana"


def _id() -> uuid.UUID:
    return uuid.uuid4()


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def _old_ts(hours: int = 73) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


@pytest.mark.asyncio
class TestS7Integration:

    async def _create_chain(
        self, db_session, entry_price: float = 100.0, strategy: str = "test_strat",
        mint: str | None = None,
    ) -> tuple[SmartWallet, SolanaWalletTrade, ResearchTrade]:
        mint = mint or f"mint_{_id().hex[:12]}"
        w = SmartWallet(id=_id(), wallet_address=f"wallet_{_id().hex[:12]}", source="test", first_seen_at=_ts())
        db_session.add(w)
        await db_session.flush()
        wt = SolanaWalletTrade(
            id=_id(), wallet_id=w.id, tx_signature=f"tx_{_id().hex[:12]}",
            mint_address=mint, side="buy", size_usd=1000.0, price_usd=entry_price,
            block_time=_ts(),
        )
        db_session.add(wt)
        await db_session.flush()
        rt = ResearchTrade(
            id=_id(), signal_id=f"sig_{_id().hex[:12]}", strategy=strategy,
            wallet_trade_id=wt.id, entry_price=entry_price, confidence=0.8,
            status="open", opened_at=_ts(),
        )
        db_session.add(rt)
        await db_session.commit()
        return w, wt, rt

    # ── S7-01: End-to-End Shadow Validation Flow ──

    async def test_open_position(self, db_session):
        _, _, rt = await self._create_chain(db_session)
        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(rt)
        assert pos is not None
        assert pos.research_trade_id == rt.id
        assert pos.strategy == rt.strategy
        assert pos.status == "open"
        assert pos.entry_price == float(rt.entry_price)
        assert pos.current_price == float(rt.entry_price)
        assert pos.tp_price > pos.entry_price
        assert pos.sl_price < pos.entry_price
        assert pos.net_pnl_usd == 0.0
        assert pos.gross_pnl_usd == 0.0

    async def test_duplicate_replay(self, db_session):
        _, _, rt = await self._create_chain(db_session)
        svc = ShadowPortfolioService(db_session)
        pos1 = await svc.open_from_research_trade(rt)
        pos2 = await svc.open_from_research_trade(rt)
        assert pos1 is not None and pos2 is not None
        assert pos1.id == pos2.id
        repo = ShadowPositionRepository(db_session)
        assert len(await repo.list_open()) == 1

    async def test_price_update_end_to_end(self, db_session, monkeypatch):
        _, _, rt = await self._create_chain(db_session, entry_price=100.0)
        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(rt)

        async def mock_resolve(self, mint: str) -> PriceResult:
            return PriceResult(price=Decimal("150.0"), source="test")
        monkeypatch.setattr(PriceTrackingService, "resolve_price", mock_resolve)
        updated = await svc.update_prices()
        assert updated == 1

        repo = ShadowPositionRepository(db_session)
        pos2 = await repo.get_by_id(pos.id)
        assert float(pos2.current_price) == 150.0

    async def test_take_profit_path(self, db_session, client, monkeypatch):
        _, _, rt = await self._create_chain(db_session, entry_price=100.0)
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)

        async def mock_resolve(self, mint: str) -> PriceResult:
            return PriceResult(price=Decimal("150.0"), source="test")
        monkeypatch.setattr(PriceTrackingService, "resolve_price", mock_resolve)
        await svc.update_prices()
        closed = await svc.evaluate_all()
        assert len(closed) == 1
        assert closed[0].close_reason == "take_profit"
        assert closed[0].net_pnl_usd > 0

        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["total_signals"] >= 1
        assert data["closed_positions"] >= 1
        assert data["net_roi_pct"] > 0

    async def test_stop_loss_path(self, db_session, client, monkeypatch):
        _, _, rt = await self._create_chain(db_session, entry_price=100.0)
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)

        async def mock_resolve(self, mint: str) -> PriceResult:
            return PriceResult(price=Decimal("50.0"), source="test")
        monkeypatch.setattr(PriceTrackingService, "resolve_price", mock_resolve)
        await svc.update_prices()
        closed = await svc.evaluate_all()
        assert len(closed) == 1
        assert closed[0].close_reason == "stop_loss"
        assert closed[0].net_pnl_usd < 0

        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["closed_positions"] >= 1

    async def test_timeout_path(self, db_session, client):
        _, _, rt = await self._create_chain(db_session, entry_price=100.0)
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)

        await db_session.execute(
            update(ShadowPosition)
            .where(ShadowPosition.research_trade_id == rt.id)
            .values(opened_at=_old_ts(settings.SOLANA_SHADOW_TIMEOUT_HOURS + 2)),
        )
        await db_session.commit()

        closed = await svc.evaluate_all()
        assert len(closed) == 1
        assert closed[0].close_reason == "timeout"

        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["closed_positions"] >= 1

    async def test_price_unavailable_no_crash(self, db_session, monkeypatch):
        _, _, rt = await self._create_chain(db_session, entry_price=100.0)
        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(rt)

        async def mock_resolve(mint: str) -> PriceResult:
            return PriceResult(price=None, source="unavailable")
        monkeypatch.setattr(PriceTrackingService, "resolve_price", mock_resolve)
        updated = await svc.update_prices()
        assert updated == 0

        repo = ShadowPositionRepository(db_session)
        pos2 = await repo.get_by_id(pos.id)
        assert pos2.current_price == 100.0
        assert pos2.status == "open"

    async def test_eval_hold(self, db_session):
        _, _, rt = await self._create_chain(db_session, entry_price=100.0)
        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(rt)

        repo = ShadowPositionRepository(db_session)
        await repo.update_current_price(pos.id, 110.0)
        closed = await svc.evaluate_all()
        assert len(closed) == 0

        pos2 = await repo.get_by_id(pos.id)
        assert pos2.status == "open"

    async def test_stats_after_closed_positions(self, db_session, client):
        for strat in ["alpha", "beta"]:
            _, _, rt = await self._create_chain(db_session, entry_price=100.0, strategy=strat)
            svc = ShadowPortfolioService(db_session)
            await svc.open_from_research_trade(rt)

        positions = await ShadowPositionRepository(db_session).list_open()
        for pos in positions:
            await ShadowPositionRepository(db_session).close_position(
                pos.id, float(pos.entry_price) * 1.1, 1000.0, 800.0, "take_profit",
            )

        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["total_signals"] >= 2
        assert data["closed_positions"] >= 2
        assert data["net_roi_pct"] > 0

    async def test_performance_after_close(self, db_session, client):
        _, _, rt = await self._create_chain(db_session, entry_price=100.0, strategy="test_perf")
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)
        repo = ShadowPositionRepository(db_session)
        pos = (await repo.list_open())[0]
        await repo.close_position(pos.id, 110.0, 500.0, 400.0, "take_profit")

        resp = await client.get(f"{SIGNALS_URL}/performance", headers={"x-admin-key": "test"})
        data = resp.json()
        strategies = [r["strategy"] for r in data]
        assert "test_perf" in strategies

    async def test_concentration_after_tp(self, db_session, client):
        _, _, rt = await self._create_chain(db_session, entry_price=100.0, strategy="test_conc")
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)
        await ShadowPositionRepository(db_session).close_position(
            (await ShadowPositionRepository(db_session).list_open())[0].id,
            110.0, 500.0, 400.0, "take_profit",
        )

        resp = await client.get(f"{SIGNALS_URL}/concentration", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["top_wallet_share_pct"] is not None

    async def test_wallet_universe_after_close(self, db_session, client):
        _, _, rt = await self._create_chain(db_session, entry_price=100.0, strategy="test_uni")
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)
        await ShadowPositionRepository(db_session).close_position(
            (await ShadowPositionRepository(db_session).list_open())[0].id,
            110.0, 500.0, 400.0, "take_profit",
        )

        resp = await client.get(f"{SIGNALS_URL}/wallet-universe", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["observed_wallets"] >= 1

    async def test_complex_flow_mixed_strategies(self, db_session, client):
        for i, (strat, entry) in enumerate([("s1", 100.0), ("s1", 200.0), ("s2", 50.0)]):
            _, _, rt = await self._create_chain(db_session, entry_price=entry, strategy=strat)
            svc = ShadowPortfolioService(db_session)
            await svc.open_from_research_trade(rt)

        repos = ShadowPositionRepository(db_session)
        all_open = await repos.list_open()
        await repos.close_position(all_open[0].id, 90.0, -100.0, -120.0, "stop_loss")
        await repos.close_position(all_open[1].id, 250.0, 500.0, 450.0, "take_profit")

        stats = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        sd = stats.json()
        assert sd["total_signals"] == 3
        assert sd["closed_positions"] == 2
        assert sd["open_positions"] == 1

        perf = await client.get(f"{SIGNALS_URL}/performance", headers={"x-admin-key": "test"})
        pd = perf.json()
        strat_names = {r["strategy"] for r in pd}
        assert "s1" in strat_names
        assert "s2" in strat_names

    # ── S7-02: Metrics Validation ──

    async def test_shadow_positions_metric(self, db_session):
        from app.core.metrics import solana_shadow_positions_total

        before_open = solana_shadow_positions_total.labels(status="open")._value.get()
        before_closed = solana_shadow_positions_total.labels(status="closed")._value.get()

        _, _, rt = await self._create_chain(db_session)
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)

        assert solana_shadow_positions_total.labels(status="open")._value.get() == before_open + 1

    async def test_shadow_pnl_gauge_negative(self, db_session):
        from app.core.metrics import solana_shadow_pnl_total

        strat = "test_pnl_neg"
        _, _, rt = await self._create_chain(db_session, entry_price=100.0, strategy=strat)
        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(rt)

        repo = ShadowPositionRepository(db_session)
        pos = (await repo.list_open())[0]
        await repo.update_price(pos.id, 80.0, -2000.0, -2150.0)

        net = await repo.net_pnl_total_by_strategy(strat)
        solana_shadow_pnl_total.labels(strategy=strat).set(net)
        assert solana_shadow_pnl_total.labels(strategy=strat)._value.get() < 0

    async def test_price_source_metrics_labels(self, db_session, monkeypatch):
        from app.core.metrics import solana_price_source_total

        for source in ("redis", "birdeye", "dexscreener", "stale", "unavailable"):
            label = solana_price_source_total.labels(source=source)
            val = label._value.get()
            assert val >= 0
            assert isinstance(val, (int, float))

    async def test_validation_requests_metric(self, db_session, client, monkeypatch):
        from app.core.metrics import solana_validation_requests_total

        for ep in ("stats", "performance", "concentration", "wallet-universe"):
            before = solana_validation_requests_total.labels(endpoint=ep)._value.get()
            await client.get(f"{SIGNALS_URL}/{ep}", headers={"x-admin-key": "test"})
            after = solana_validation_requests_total.labels(endpoint=ep)._value.get()
            assert after == before + 1

    async def test_no_negative_counters(self):
        from app.core.metrics import (
            solana_shadow_evals_total,
            solana_price_source_total,
            solana_price_update_total,
            solana_price_stale_total,
            solana_validation_requests_total,
        )
        labeled = [
            (solana_shadow_evals_total, {"result": "held"}),
            (solana_price_source_total, {"source": "redis"}),
            (solana_price_source_total, {"source": "birdeye"}),
            (solana_price_source_total, {"source": "dexscreener"}),
            (solana_price_source_total, {"source": "stale"}),
            (solana_price_source_total, {"source": "unavailable"}),
            (solana_validation_requests_total, {"endpoint": "stats"}),
        ]
        unlabeled = [solana_price_update_total, solana_price_stale_total]
        for metric, labels in labeled:
            val = metric.labels(**labels)._value.get()
            assert val >= 0, f"{metric._name}{labels} = {val}"
        for metric in unlabeled:
            val = metric._value.get()
            assert val >= 0, f"{metric._name} = {val}"
