import asyncio
import uuid
from app.core.events import EventBus
from app.database import async_session_factory
from app.models import Market

async def seed():
    # Use a unique condition_id each time to avoid cooldown or duplicate market rejections
    condition_id = "0x" + uuid.uuid4().hex
    async with async_session_factory() as db:
        market = Market(
            id=uuid.uuid4(),
            condition_id=condition_id,
            title="Will E2E pass?",
            slug="will-e2e-pass-" + condition_id[:8]
        )
        db.add(market)
        await db.commit()
        print(f"Market created: {condition_id}")

    data = {
        "block_number": 88164876,
        "transaction_hash": "0x" + "a" * 64,
        "from": "0x7b6d19488349254d36e7887719602e8587635c43",
        "to": "0xE111180000d2663C0091e4f400237545B87B996B",
        "side": "buy",
        "size": 500, # Smaller size to avoid exceeding max position size (10% of 10000 = 1000)
        "price": 0.55,
        "condition_id": condition_id,
        "outcome": "YES"
    }
    await EventBus.publish("market:data", "onchain_trade", "seed_script", data)
    print("Seed event published")

if __name__ == "__main__":
    asyncio.run(seed())
