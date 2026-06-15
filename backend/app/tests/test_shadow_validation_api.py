import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.models.research_trade import ResearchTrade
from app.models.shadow_position import ShadowPosition
from app.models.smart_wallet import SmartWallet
from app.models.wallet_trade import SolanaWalletTrade
from app.config import settings

SIGNALS_URL = "/api/v1/signals/solana"


def _make_id() -> uuid.UUID:
    return uuid.uuid4()


def _ts() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
class TestShadowValidationAPI:

    async def _seed_wallet(self, db_session, address: str) -> SmartWallet:
        w = SmartWallet(id=_make_id(), wallet_address=address, source="test", first_seen_at=_ts())
        db_session.add(w)
        await db_session.flush()
        return w

    async def _seed_wallet_trade(self, db_session, wallet: SmartWallet) -> SolanaWalletTrade:
        wt = SolanaWalletTrade(
            id=_make_id(), wallet_id=wallet.id, tx_signature=f"tx_{_make_id().hex[:8]}",
            mint_address=f"mint_{_make_id().hex[:8]}", side="buy",
            size_usd=1000.0, price_usd=2.0, block_time=_ts(),
        )
        db_session.add(wt)
        await db_session.flush()
        return wt

    async def _seed_research_trade(self, db_session, wallet_trade: SolanaWalletTrade, strategy: str) -> ResearchTrade:
        rt = ResearchTrade(
            id=_make_id(), signal_id=f"sig_{_make_id().hex[:8]}", strategy=strategy,
            wallet_trade_id=wallet_trade.id, entry_price=100.0, confidence=0.8,
            status="closed", opened_at=_ts(),
        )
        db_session.add(rt)
        await db_session.flush()
        return rt

    async def _seed_position(
        self, db_session, strategy: str, net_pnl: float | None, size_usd: float = 1000.0,
        status: str = "closed", wallet_address: str | None = None,
    ) -> ShadowPosition:
        if wallet_address is None:
            wallet_address = f"wallet_{_make_id().hex[:8]}"
        wallet = await self._seed_wallet(db_session, wallet_address)
        wt = await self._seed_wallet_trade(db_session, wallet)
        rt = await self._seed_research_trade(db_session, wt, strategy)
        sp = ShadowPosition(
            id=_make_id(), research_trade_id=rt.id, strategy=strategy,
            entry_price=100.0, size_usd=size_usd, current_price=100.0,
            net_pnl_usd=net_pnl, gross_pnl_usd=net_pnl,
            status=status, opened_at=_ts(),
            closed_at=_ts() if status == "closed" else None,
        )
        db_session.add(sp)
        await db_session.commit()
        return sp

    # ── Stats ──

    async def test_stats_empty(self, client: AsyncClient, db_session):
        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_signals"] == 0
        assert data["open_positions"] == 0
        assert data["closed_positions"] == 0
        assert data["net_roi_pct"] == 0.0
        assert data["profit_factor"] is None
        assert data["win_rate_pct"] == 0.0

    async def test_stats_basic_counts(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=None, status="open")
        await self._seed_position(db_session, "s1", net_pnl=None, status="open")
        await self._seed_position(db_session, "s2", net_pnl=50.0, status="closed")
        await self._seed_position(db_session, "s2", net_pnl=30.0, status="closed")
        await self._seed_position(db_session, "s2", net_pnl=-10.0, status="closed")

        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["total_signals"] == 5
        assert data["open_positions"] == 2
        assert data["closed_positions"] == 3

    async def test_stats_roi_positive(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=80.0, size_usd=1000.0)
        await self._seed_position(db_session, "s1", net_pnl=20.0, size_usd=1000.0)

        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["net_roi_pct"] == 5.0

    async def test_stats_roi_negative(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=-50.0, size_usd=1000.0)

        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["net_roi_pct"] == -5.0

    async def test_stats_profit_factor(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=200.0)
        await self._seed_position(db_session, "s1", net_pnl=-50.0)

        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["profit_factor"] == 4.0

    async def test_stats_zero_losses(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=100.0)

        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["profit_factor"] is None

    async def test_stats_zero_size(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=50.0, size_usd=0.0)

        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["net_roi_pct"] == 0.0
        assert data["profit_factor"] is None

    async def test_stats_win_rate(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=100.0)
        await self._seed_position(db_session, "s1", net_pnl=50.0)
        await self._seed_position(db_session, "s1", net_pnl=-30.0)
        await self._seed_position(db_session, "s1", net_pnl=-20.0)

        resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["win_rate_pct"] == 50.0

    # ── Performance ──

    async def test_performance_grouping(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "strat_a", net_pnl=100.0)
        await self._seed_position(db_session, "strat_a", net_pnl=50.0)
        await self._seed_position(db_session, "strat_b", net_pnl=200.0)

        resp = await client.get(f"{SIGNALS_URL}/performance", headers={"x-admin-key": "test"})
        data = resp.json()
        assert len(data) == 2
        a = next(r for r in data if r["strategy"] == "strat_a")
        b = next(r for r in data if r["strategy"] == "strat_b")
        assert a["positions"] == 2
        assert b["positions"] == 1
        assert a["net_pnl_usd"] == 150.0
        assert b["net_pnl_usd"] == 200.0

    async def test_performance_ordering(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "strat_b", net_pnl=50.0)
        await self._seed_position(db_session, "strat_a", net_pnl=100.0)
        await self._seed_position(db_session, "strat_c", net_pnl=75.0)

        resp = await client.get(f"{SIGNALS_URL}/performance", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data[0]["strategy"] == "strat_a"
        assert data[1]["strategy"] == "strat_c"
        assert data[2]["strategy"] == "strat_b"

    async def test_performance_avg_return(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=50.0, size_usd=1000.0)
        await self._seed_position(db_session, "s1", net_pnl=150.0, size_usd=1000.0)

        resp = await client.get(f"{SIGNALS_URL}/performance", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data[0]["avg_return_pct"] == 10.0

    # ── Concentration ──

    async def test_concentration_single_wallet(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=100.0, wallet_address="w1")

        resp = await client.get(f"{SIGNALS_URL}/concentration", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["top_wallet_share_pct"] == 100.0
        assert data["top_5_wallet_share_pct"] == 100.0

    async def test_concentration_multiple_wallets(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=300.0, wallet_address="w1")
        await self._seed_position(db_session, "s1", net_pnl=100.0, wallet_address="w2")
        await self._seed_position(db_session, "s1", net_pnl=100.0, wallet_address="w3")

        resp = await client.get(f"{SIGNALS_URL}/concentration", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["top_wallet_share_pct"] == 60.0
        assert data["top_5_wallet_share_pct"] == 100.0

    async def test_concentration_empty(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=-50.0, wallet_address="w1")

        resp = await client.get(f"{SIGNALS_URL}/concentration", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["top_wallet_share_pct"] is None
        assert data["top_5_wallet_share_pct"] is None

    # ── Wallet Universe ──

    async def test_wallet_universe_basic(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=100.0, wallet_address="w1")
        await self._seed_position(db_session, "s1", net_pnl=50.0, wallet_address="w2")
        await self._seed_position(db_session, "s1", net_pnl=-20.0, wallet_address="w3")

        resp = await client.get(f"{SIGNALS_URL}/wallet-universe", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["observed_wallets"] == 3
        assert data["active_wallets"] == 3

    async def test_wallet_universe_top_ordering(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=10.0, wallet_address="w_a")
        await self._seed_position(db_session, "s1", net_pnl=200.0, wallet_address="w_b")
        await self._seed_position(db_session, "s1", net_pnl=50.0, wallet_address="w_c")

        resp = await client.get(f"{SIGNALS_URL}/wallet-universe", headers={"x-admin-key": "test"})
        data = resp.json()
        wallets = data["top_wallets"]
        assert wallets[0]["wallet"] == "w_b"
        assert wallets[1]["wallet"] == "w_c"
        assert wallets[2]["wallet"] == "w_a"

    async def test_wallet_universe_activation_rate(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=50.0, wallet_address="w_active1")
        await self._seed_position(db_session, "s1", net_pnl=30.0, wallet_address="w_active2")
        await self._seed_position(db_session, "s1", net_pnl=None, status="open", wallet_address="w_obs_only")

        resp = await client.get(f"{SIGNALS_URL}/wallet-universe", headers={"x-admin-key": "test"})
        data = resp.json()
        assert data["observed_wallets"] == 2
        assert data["active_wallets"] == 2
        assert data["activation_rate_pct"] == 100.0

    # ── Auth ──

    async def test_admin_auth_missing(self, client: AsyncClient, db_session):
        current_key = settings.ADMIN_API_KEY
        if not current_key:
            with patch.object(settings, "ADMIN_API_KEY", "secret"):
                resp = await client.get(f"{SIGNALS_URL}/stats")
            assert resp.status_code == 403
        else:
            resp = await client.get(f"{SIGNALS_URL}/stats")
            assert resp.status_code == 403

    async def test_admin_auth_wrong(self, client: AsyncClient, db_session):
        current_key = settings.ADMIN_API_KEY
        if not current_key:
            with patch.object(settings, "ADMIN_API_KEY", "secret"):
                resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "wrong"})
            assert resp.status_code == 403
        else:
            resp = await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "wrong"})
            assert resp.status_code == 403

    # ── Metrics ──

    async def test_metrics_increment(self, client: AsyncClient, db_session):
        from app.core.metrics import solana_validation_requests_total

        before = solana_validation_requests_total.labels(endpoint="stats")._value.get()
        await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        after = solana_validation_requests_total.labels(endpoint="stats")._value.get()
        assert after == before + 1

    # ── No mutation ──

    async def test_no_mutation_side_effects(self, client: AsyncClient, db_session):
        await self._seed_position(db_session, "s1", net_pnl=50.0, wallet_address="w_no_mut")

        from app.repositories.shadow_position_repository import ShadowPositionRepository
        repo = ShadowPositionRepository(db_session)
        before = await repo.list_open()

        await client.get(f"{SIGNALS_URL}/stats", headers={"x-admin-key": "test"})
        await client.get(f"{SIGNALS_URL}/performance", headers={"x-admin-key": "test"})
        await client.get(f"{SIGNALS_URL}/concentration", headers={"x-admin-key": "test"})
        await client.get(f"{SIGNALS_URL}/wallet-universe", headers={"x-admin-key": "test"})

        after = await repo.list_open()
        assert len(before) == len(after)
