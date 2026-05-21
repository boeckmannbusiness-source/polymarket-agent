"""Seed database with sample data for development."""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from app.database import async_session_factory, engine
from app.core.logging import setup_logging, logger
from app.models import Market, Wallet, WalletScore, Signal, Trade


async def seed():
    setup_logging()
    logger.info("seeding_database")

    async with async_session_factory() as db:
        market = Market(
            id=uuid.uuid4(),
            condition_id="0x" + "a" * 64,
            slug="btc-100k-2026",
            title="Will BTC reach $100k by end of 2026?",
            description="Market on whether Bitcoin will reach $100,000 by December 31, 2026.",
            outcomes={"YES": "0xabc", "NO": "0xdef"},
            volume=1_500_000,
            liquidity=500_000,
            clob_token_ids=["123", "456"],
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc) + timedelta(days=200),
        )
        db.add(market)

        wallet = Wallet(
            address="0x1234567890abcdef1234567890abcdef12345678",
            total_trades=150,
            total_volume=500_000,
            realized_pnl=45_000,
            win_count=98,
            loss_count=52,
            win_rate=0.6533,
            current_rank=12,
            tags=["whale", "smart_money"],
        )
        db.add(wallet)

        wallet2 = Wallet(
            address="0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            total_trades=89,
            total_volume=320_000,
            realized_pnl=-12_000,
            win_count=38,
            loss_count=51,
            win_rate=0.4269,
            current_rank=145,
            tags=["contrarian"],
        )
        db.add(wallet2)

        score = WalletScore(
            wallet_address=wallet.address,
            score_type="overall",
            score=0.78,
            confidence=0.92,
            period_end=datetime.now(timezone.utc),
        )
        db.add(score)

        signal = Signal(
            id=uuid.uuid4(),
            market_id=market.id,
            signal_type="whale_behavior",
            direction="bullish",
            confidence=0.82,
            implied_probability=0.65,
            estimated_probability=0.78,
            reasoning="Whale wallet 0x1234...5678 accumulated 50k YES over 48h. Historical accuracy 78%.",
            source_agent="signal_agent",
            is_active=True,
        )
        db.add(signal)

        trade = Trade(
            id=uuid.uuid4(),
            market_id=market.id,
            signal_id=signal.id,
            trade_type="paper",
            status="open",
            side="buy",
            outcome="YES",
            size=1000,
            price=0.65,
            filled_size=1000,
            filled_price=0.6523,
            slippage=0.0035,
            fee=0.65,
            entry_timestamp=datetime.now(timezone.utc),
            stop_loss=0.55,
            take_profit=0.98,
            reason="Following whale accumulation signal",
            agent_id="signal_agent",
        )
        db.add(trade)

        await db.commit()
        logger.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(seed())
