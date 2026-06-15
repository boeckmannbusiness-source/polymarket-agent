import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shadow_position import ShadowPosition
from app.models.research_trade import ResearchTrade
from app.repositories.shadow_position_repository import ShadowPositionRepository
from app.services.shadow_portfolio_service import ShadowPortfolioService, _compute_pnl
from app.config import settings


def _make_research_trade(
    db_session,
    strategy="high_score_entry",
    entry_price=100.0,
    signal_id=None,
    status="open",
) -> ResearchTrade:
    trade = ResearchTrade(
        id=uuid.uuid4(),
        signal_id=signal_id or f"sig_{uuid.uuid4().hex[:8]}",
        strategy=strategy,
        entry_price=entry_price,
        confidence=0.8,
        status=status,
        opened_at=datetime.now(timezone.utc),
    )
    db_session.add(trade)
    return trade


class TestPnlFormula:
    def test_compute_pnl_positive(self):
        gross, net = _compute_pnl(entry_price=100.0, exit_price=110.0, size_usd=10000.0)
        quantity = 10000.0 / 100.0
        expected_gross = round((110.0 - 100.0) * quantity, 2)
        expected_net = round(expected_gross - 10000.0 * 0.0075 - 10000.0 * 0.0075, 2)
        assert gross == expected_gross
        assert net == expected_net
        assert net < gross

    def test_compute_pnl_negative(self):
        gross, net = _compute_pnl(entry_price=100.0, exit_price=90.0, size_usd=10000.0)
        quantity = 10000.0 / 100.0
        expected_gross = round((90.0 - 100.0) * quantity, 2)
        expected_net = round(expected_gross - 10000.0 * 0.0075 - 10000.0 * 0.0075, 2)
        assert gross == expected_gross
        assert net < expected_gross

    def test_compute_pnl_zero_entry(self):
        gross, net = _compute_pnl(entry_price=0.0, exit_price=10.0, size_usd=1000.0)
        assert gross == 0.0
        assert net == round(0 - 1000.0 * 0.0075 - 1000.0 * 0.0075, 2)


@pytest.mark.asyncio
class TestShadowPositionModel:
    async def test_create_shadow_position(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session)
        await db_session.flush()

        pos = ShadowPosition(
            id=uuid.uuid4(),
            research_trade_id=research_trade.id,
            strategy=research_trade.strategy,
            entry_price=100.0,
            size_usd=10000.0,
            current_price=100.0,
            tp_price=115.0,
            sl_price=90.0,
            gross_pnl_usd=0.0,
            net_pnl_usd=0.0,
            status="open",
            opened_at=datetime.now(timezone.utc),
        )
        db_session.add(pos)
        await db_session.commit()

        assert pos.id is not None
        assert pos.research_trade_id == research_trade.id
        assert pos.strategy == "high_score_entry"
        assert pos.entry_price == 100.0
        assert pos.status == "open"
        assert pos.net_pnl_usd == 0.0

    async def test_defaults(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session)
        await db_session.flush()

        pos = ShadowPosition(
            id=uuid.uuid4(),
            research_trade_id=research_trade.id,
            strategy=research_trade.strategy,
            entry_price=50.0,
            size_usd=5000.0,
            opened_at=datetime.now(timezone.utc),
        )
        db_session.add(pos)
        await db_session.commit()

        assert pos.status == "open"
        assert pos.close_reason is None
        assert pos.closed_at is None
        assert pos.gross_pnl_usd is None
        assert pos.net_pnl_usd is None

    async def test_unique_constraint_research_trade(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session)
        await db_session.flush()

        pos1 = ShadowPosition(
            id=uuid.uuid4(),
            research_trade_id=research_trade.id,
            strategy="strat_a",
            entry_price=100.0,
            size_usd=1000.0,
            opened_at=datetime.now(timezone.utc),
        )
        db_session.add(pos1)
        await db_session.commit()

        pos2 = ShadowPosition(
            id=uuid.uuid4(),
            research_trade_id=research_trade.id,
            strategy="strat_a",
            entry_price=200.0,
            size_usd=2000.0,
            opened_at=datetime.now(timezone.utc),
        )
        db_session.add(pos2)
        with pytest.raises(Exception):
            await db_session.commit()

    async def test_check_constraint_status(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session)
        await db_session.flush()

        pos = ShadowPosition(
            id=uuid.uuid4(),
            research_trade_id=research_trade.id,
            strategy="s1",
            entry_price=100.0,
            size_usd=1000.0,
            status="invalid_status",
            opened_at=datetime.now(timezone.utc),
        )
        db_session.add(pos)
        with pytest.raises(Exception):
            await db_session.commit()


@pytest.mark.asyncio
class TestShadowPositionRepository:
    async def test_create_and_get_by_id(self, db_session: AsyncSession):
        repo = ShadowPositionRepository(db_session)
        research_trade = _make_research_trade(db_session)
        await db_session.flush()

        pos = ShadowPosition(
            id=uuid.uuid4(),
            research_trade_id=research_trade.id,
            strategy="strat_a",
            entry_price=100.0,
            size_usd=5000.0,
            opened_at=datetime.now(timezone.utc),
        )
        created = await repo.create(pos)
        assert created.id is not None

        found = await repo.get_by_id(created.id)
        assert found is not None
        assert found.research_trade_id == research_trade.id

    async def test_get_by_research_trade(self, db_session: AsyncSession):
        repo = ShadowPositionRepository(db_session)
        research_trade = _make_research_trade(db_session, signal_id="sig_get_by_rt")
        await db_session.flush()

        created = await repo.create(ShadowPosition(
            id=uuid.uuid4(),
            research_trade_id=research_trade.id,
            strategy="strat_a",
            entry_price=100.0,
            size_usd=5000.0,
            opened_at=datetime.now(timezone.utc),
        ))
        found = await repo.get_by_research_trade(research_trade.id)
        assert found is not None
        assert found.id == created.id

    async def test_list_open_filters_by_status(self, db_session: AsyncSession):
        repo = ShadowPositionRepository(db_session)
        rt1 = _make_research_trade(db_session, signal_id="sig_list1")
        rt2 = _make_research_trade(db_session, signal_id="sig_list2")
        await db_session.flush()

        await repo.create(ShadowPosition(
            id=uuid.uuid4(), research_trade_id=rt1.id, strategy="s1",
            entry_price=100.0, size_usd=1000.0, opened_at=datetime.now(timezone.utc),
        ))
        closed_pos = await repo.create(ShadowPosition(
            id=uuid.uuid4(), research_trade_id=rt2.id, strategy="s2",
            entry_price=200.0, size_usd=2000.0, opened_at=datetime.now(timezone.utc),
        ))
        await repo.close_position(closed_pos.id, 200.0, 0.0, -75.0, "stop_loss")

        open_positions = await repo.list_open()
        assert len(open_positions) == 1

    async def test_close_position_sets_fields(self, db_session: AsyncSession):
        repo = ShadowPositionRepository(db_session)
        research_trade = _make_research_trade(db_session, signal_id="sig_close")
        await db_session.flush()

        pos = await repo.create(ShadowPosition(
            id=uuid.uuid4(), research_trade_id=research_trade.id, strategy="s1",
            entry_price=100.0, size_usd=1000.0, opened_at=datetime.now(timezone.utc),
        ))
        result = await repo.close_position(pos.id, 115.0, 150.0, 135.0, "take_profit")
        assert result is not None
        assert result.status == "closed"
        assert result.close_reason == "take_profit"
        assert float(result.exit_price) == 115.0
        assert float(result.gross_pnl_usd) == 150.0
        assert float(result.net_pnl_usd) == 135.0

    async def test_update_price_sets_gross_and_net(self, db_session: AsyncSession):
        repo = ShadowPositionRepository(db_session)
        research_trade = _make_research_trade(db_session, signal_id="sig_price")
        await db_session.flush()

        pos = await repo.create(ShadowPosition(
            id=uuid.uuid4(), research_trade_id=research_trade.id, strategy="s1",
            entry_price=100.0, size_usd=1000.0, opened_at=datetime.now(timezone.utc),
        ))
        result = await repo.update_price(pos.id, 110.0, 100.0, 85.0)
        assert result is not None
        assert float(result.current_price) == 110.0
        assert float(result.gross_pnl_usd) == 100.0
        assert float(result.net_pnl_usd) == 85.0

    async def test_net_pnl_total_by_strategy(self, db_session: AsyncSession):
        repo = ShadowPositionRepository(db_session)
        rt = _make_research_trade(db_session, strategy="momentum")
        await db_session.flush()

        await repo.create(ShadowPosition(
            id=uuid.uuid4(), research_trade_id=rt.id, strategy="momentum",
            entry_price=100.0, size_usd=5000.0, opened_at=datetime.now(timezone.utc),
            net_pnl_usd=250.0, gross_pnl_usd=325.0,
        ))
        total = await repo.net_pnl_total_by_strategy("momentum")
        assert total == 250.0


@pytest.mark.asyncio
class TestShadowPortfolioService:
    async def test_open_from_research_trade(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session)
        await db_session.flush()

        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(research_trade)
        assert pos is not None
        assert pos.research_trade_id == research_trade.id
        assert pos.strategy == "high_score_entry"
        assert float(pos.entry_price) == 100.0
        assert float(pos.tp_price) > 100.0
        assert float(pos.sl_price) < 100.0
        assert pos.status == "open"
        assert float(pos.gross_pnl_usd) == 0.0
        assert float(pos.net_pnl_usd) == 0.0

    async def test_open_idempotent(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session)
        await db_session.flush()

        svc = ShadowPortfolioService(db_session)
        pos1 = await svc.open_from_research_trade(research_trade)
        pos2 = await svc.open_from_research_trade(research_trade)
        assert pos1.id == pos2.id

    async def test_open_rejects_zero_size(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session, entry_price=0.0)
        await db_session.flush()

        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(research_trade, size_usd=0.0)
        assert pos is None

    async def test_open_rejects_zero_entry(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session, entry_price=0.0)
        await db_session.flush()

        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(research_trade)
        assert pos is None

    async def test_evaluate_take_profit(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session, entry_price=100.0)
        await db_session.flush()

        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(
            research_trade, tp_pct=0.05, sl_pct=0.10,
        )
        tp = float(pos.tp_price)
        gross, net = (105.0, 85.0)  # pre-computed for 5% TP at entry=100, size=10000
        repo = ShadowPositionRepository(db_session)
        await repo.update_price(pos.id, 106.0, gross, net)

        closed = await svc.evaluate_all()
        assert len(closed) == 1
        assert closed[0].close_reason == "take_profit"
        assert float(closed[0].exit_price) == tp

    async def test_evaluate_stop_loss(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session, entry_price=100.0)
        await db_session.flush()

        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(
            research_trade, tp_pct=0.10, sl_pct=0.05,
        )
        sl = float(pos.sl_price)
        repo = ShadowPositionRepository(db_session)
        await repo.update_price(pos.id, 94.0, -600.0, -750.0)

        closed = await svc.evaluate_all()
        assert len(closed) == 1
        assert closed[0].close_reason == "stop_loss"
        assert float(closed[0].exit_price) == sl

    async def test_evaluate_hold(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session, entry_price=100.0)
        await db_session.flush()

        svc = ShadowPortfolioService(db_session)
        await svc.open_from_research_trade(
            research_trade, tp_pct=0.20, sl_pct=0.20,
        )
        repo = ShadowPositionRepository(db_session)
        all_pos = await repo.list_open()
        await repo.update_price(all_pos[0].id, 105.0, 500.0, 425.0)

        closed = await svc.evaluate_all()
        assert len(closed) == 0

    async def test_evaluate_timeout(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session, entry_price=100.0)
        await db_session.flush()

        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(research_trade)

        repo = ShadowPositionRepository(db_session)
        far_past = datetime.now(timezone.utc) - timedelta(hours=73)
        pos.opened_at = far_past
        db_session.add(pos)
        await db_session.commit()

        closed = await svc.evaluate_all()
        assert len(closed) == 1
        assert closed[0].close_reason == "timeout"

    async def test_close_position_manual(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session)
        await db_session.flush()

        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(research_trade)

        result = await svc.close_position(pos.id, reason="manual")
        assert result is not None
        assert result.status == "closed"
        assert result.close_reason == "manual"

    async def test_close_already_closed(self, db_session: AsyncSession):
        research_trade = _make_research_trade(db_session)
        await db_session.flush()

        svc = ShadowPortfolioService(db_session)
        pos = await svc.open_from_research_trade(research_trade)
        await svc.close_position(pos.id, reason="manual")
        result = await svc.close_position(pos.id, reason="manual")
        assert result is None
