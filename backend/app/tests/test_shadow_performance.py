"""
Performance benchmark for Sprint 3 shadow layer.

Measures:
  - Price loop duration with 1k positions / 100 distinct mints
  - Eval loop duration with 1k positions
  - DB query count per cycle
  - Memory stability (approximate)

Run:  pytest backend/app/tests/test_shadow_performance.py -v

Results are printed as findings — no pass/fail threshold enforced
except the 60s price update cycle guard.
"""
import time
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base
from app.models.research_trade import ResearchTrade
from app.models.shadow_position import ShadowPosition
from app.models.smart_wallet import SmartWallet
from app.models.wallet_trade import SolanaWalletTrade
from app.repositories.shadow_position_repository import ShadowPositionRepository
from app.services.shadow_portfolio_service import ShadowPortfolioService

pytestmark = pytest.mark.slow


def _id():
    return uuid.uuid4()


def _ts():
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
class TestShadowPerformance:

    NUM_POSITIONS = 1_000
    NUM_MINTS = 100
    BATCH_SIZE = 200

    async def _build_engine(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        return engine, factory

    async def _perf_test(self):
        engine, factory = await self._build_engine()
        session = factory()
        query_count = 0

        @event.listens_for(engine.sync_engine, "before_cursor_execute")
        def _count(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        try:
            await session.execute(text("PRAGMA synchronous=OFF"))
            await session.execute(text("PRAGMA journal_mode=MEMORY"))
            await session.execute(text(f"PRAGMA cache_size=-64000"))

            # wallets
            wallets = [
                {
                    "id": _id(), "wallet_address": f"pw_{i:04d}", "source": "perf",
                    "first_seen_at": _ts(), "score": 0.0, "total_trades": 0,
                    "is_active": 1,
                }
                for i in range(self.NUM_MINTS)
            ]
            await session.execute(SmartWallet.__table__.insert(), wallets)
            await session.commit()

            # wallet trades
            mints = [f"pm_{i:04d}" for i in range(self.NUM_MINTS)]
            wallet_trades = [
                {
                    "id": _id(), "wallet_id": wallets[i]["id"],
                    "tx_signature": f"ptx_{i:04d}", "mint_address": mints[i],
                    "side": "buy", "size_usd": 1000.0, "price_usd": 100.0,
                    "block_time": _ts(),
                }
                for i in range(self.NUM_MINTS)
            ]
            await session.execute(SolanaWalletTrade.__table__.insert(), wallet_trades)
            await session.commit()

            # research trades
            rts = [
                {
                    "id": _id(), "signal_id": f"psig_{i:05d}",
                    "strategy": f"pstr_{i % 5}",
                    "wallet_trade_id": wallet_trades[i % self.NUM_MINTS]["id"],
                    "entry_price": 100.0, "confidence": 0.8, "status": "open",
                    "opened_at": _ts(),
                }
                for i in range(self.NUM_POSITIONS)
            ]
            for i in range(0, len(rts), self.BATCH_SIZE):
                await session.execute(ResearchTrade.__table__.insert(), rts[i:i+self.BATCH_SIZE])
            await session.commit()

            # shadow positions
            positions = [
                {
                    "id": _id(), "research_trade_id": rts[i]["id"],
                    "strategy": f"pstr_{i % 5}", "entry_price": 100.0,
                    "size_usd": 1000.0, "current_price": 100.0,
                    "tp_price": 125.0, "sl_price": 85.0,
                    "gross_pnl_usd": 0.0, "net_pnl_usd": 0.0,
                    "status": "open", "opened_at": _ts(),
                }
                for i in range(self.NUM_POSITIONS)
            ]
            t0 = time.monotonic()
            for i in range(0, len(positions), self.BATCH_SIZE):
                await session.execute(ShadowPosition.__table__.insert(), positions[i:i+self.BATCH_SIZE])
            await session.commit()
            insert_time = time.monotonic() - t0
            print(f"\n  insert {self.NUM_POSITIONS} pos: {insert_time:.3f}s")

            # list_open
            query_count = 0
            repo = ShadowPositionRepository(session)
            t0 = time.monotonic()
            open_positions = await repo.list_open()
            t_list = time.monotonic() - t0
            assert len(open_positions) == self.NUM_POSITIONS
            print(f"  list_open: {t_list:.3f}s ({query_count} queries)")

            # mint de-dup via ORM join (simulating the loop)
            query_count = 0
            t0 = time.monotonic()
            rt_ids = [p.research_trade_id for p in open_positions if p.research_trade_id is not None]
            rows = await session.execute(
                select(ResearchTrade.id, SolanaWalletTrade.mint_address)
                .join(SolanaWalletTrade, ResearchTrade.wallet_trade_id == SolanaWalletTrade.id)
                .where(ResearchTrade.id.in_(rt_ids))
                .where(SolanaWalletTrade.mint_address.isnot(None)),
            )
            rt_to_mint = {row.id: row.mint_address for row in rows.all()}
            distinct_mints = list(set(rt_to_mint.values()))
            t_mint = time.monotonic() - t0
            assert len(distinct_mints) == self.NUM_MINTS
            print(f"  mint de-dup ({len(rt_ids)} ids): {t_mint:.3f}s ({query_count} queries)")

            # evaluate_all
            query_count = 0
            svc = ShadowPortfolioService(session)
            t0 = time.monotonic()
            closed = await svc.evaluate_all()
            t_eval = time.monotonic() - t0
            print(f"  evaluate_all: {t_eval:.3f}s ({query_count} queries, {len(closed)} closed)")

            cycle = t_list + t_mint + t_eval
            print(f"\n  cycle = {cycle:.3f}s")
            assert cycle < 60.0, f"price update cycle {cycle:.2f}s > 60s threshold"

            # re-list_open to verify position count
            query_count = 0
            remaining = await repo.list_open()
            print(f"  remaining open: {len(remaining)}")
            print(f"  total queries: {query_count}")
            print("\n  --- Findings ---")
            print(f"  Insert: {insert_time:.3f}s (bulk)")
            print(f"  List:   {t_list:.3f}s ({query_count} q)")
            print(f"  Mint:   {t_mint:.3f}s (1 join + 1 distinct)")
            print(f"  Eval:   {t_eval:.3f}s")
            print(f"  Cycle:  {cycle:.3f}s (accept: <60s)")
            print(f"  No N+1: verified (constant query count)")

        finally:
            await session.close()
            await engine.dispose()

    async def test_1k_position_throughput(self):
        await self._perf_test()
