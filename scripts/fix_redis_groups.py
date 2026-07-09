import asyncio
from app.redis import get_redis

async def fix():
    r = await get_redis()
    groups_to_reset = [
        ("market:data", "whale_agent"),
        ("market:data", "research_agent"),
        ("wallet:trade", "signal_agent"),
        ("signal:generated", "risk_agent"),
        ("trade:request", "execution_agent"),
    ]

    for stream, group in groups_to_reset:
        try:
            await r.xgroup_setid(stream, group, "0")
            print(f"Group {group} on {stream} reset to 0")
        except Exception as e:
            print(f"Error resetting {group} on {stream}: {e}")

if __name__ == "__main__":
    asyncio.run(fix())
