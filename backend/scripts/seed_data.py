"""Seed database with sample data using SQLAlchemy ORM."""
import asyncio, uuid, random, datetime

from app.database import async_session_factory
from app.models.market import Market, MarketEvent
from app.models.wallet import Wallet, WalletTrade, WalletScore
from app.models.signal import Signal
from app.models.trade import Trade
from app.models.agent_log import AgentLog


MARKETS = [
    ("Will BTC reach $150k by June 2026?", "Bitcoin price prediction"),
    ("Will ETH 2.0 launch before July 2026?", "Ethereum upgrade"),
    ("Will Fed cut rates in Q2 2026?", "Federal reserve"),
    ("Will AI regulation pass in 2026?", "AI regulation"),
    ("Will Trump win 2028 nomination?", "US politics"),
]

WHALE_ADDRESSES = [
    "0x" + "".join(random.choices("0123456789abcdef", k=40)) for _ in range(5)
]


async def seed():
    async with async_session_factory() as session:
        now = datetime.datetime.now(datetime.timezone.utc)

        market_objs = []
        for title, desc in MARKETS:
            m = Market(
                id=uuid.uuid4(),
                condition_id="0x" + "".join(random.choices("0123456789abcdef", k=64)),
                title=title,
                description=desc,
                volume=random.uniform(500000, 5000000),
                liquidity=random.uniform(100000, 1000000),
                start_date=now - datetime.timedelta(days=30),
                end_date=now + datetime.timedelta(days=60),
                resolved=False,
            )
            session.add(m)
            market_objs.append(m)
        await session.flush()
        print(f"  + {len(MARKETS)} markets")

        for i, addr in enumerate(WHALE_ADDRESSES):
            w = Wallet(
                address=addr,
                total_volume=random.uniform(50000, 2000000),
                total_trades=random.randint(10, 500),
                tags=[f"whale_{i+1}"],
            )
            session.add(w)
            wt = WalletTrade(
                wallet_address=w.address,
                market_id=random.choice(market_objs).id,
                side="buy",
                size=random.uniform(100, 10000),
                price=random.uniform(0.1, 0.9),
                is_open=True,
                entry_timestamp=now - datetime.timedelta(days=random.randint(1, 30)),
            )
            session.add(wt)
        await session.flush()
        print(f"  + {len(WHALE_ADDRESSES)} wallets with trades")

        for m in market_objs:
            s = Signal(
                id=uuid.uuid4(),
                market_id=m.id,
                signal_type="momentum",
                direction="buy",
                confidence=random.uniform(0.6, 0.95),
                reasoning="Generated momentum signal based on whale activity and volume trends",
                source_agent="signal_agent",
                is_active=True,
                expired_at=now + datetime.timedelta(days=7),
            )
            session.add(s)
        print(f"  + {len(MARKETS)} signals")

        for m in market_objs:
            t = Trade(
                id=uuid.uuid4(),
                market_id=m.id,
                trade_type="paper",
                status="open",
                side="buy",
                outcome="YES",
                order_type="market",
                size=random.uniform(100, 5000),
                price=random.uniform(0.1, 0.9),
                filled_size=0,
                entry_timestamp=now,
            )
            session.add(t)
        print(f"  + {len(MARKETS)} paper trades")

        al = AgentLog(
            agent_name="system",
            event_type="seed_complete",
            data={"message": "Database seeded successfully", "markets": len(MARKETS)},
        )
        session.add(al)
        print("  + agent_log entry")

        await session.commit()
        print("Seed complete!")


asyncio.run(seed())
