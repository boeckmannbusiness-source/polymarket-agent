import asyncio
import os
from app.config import settings
from app.redis import get_redis
from app.database import engine
from sqlalchemy import text

async def check():
    print(f"Checking Redis at {settings.REDIS_URL}")
    try:
        r = await get_redis()
        pong = await r.ping()
        print(f"Redis Ping: {pong}")
    except Exception as e:
        print(f"Redis Error: {e}")

    print(f"Checking DB at {settings.DATABASE_URL}")
    try:
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT 1"))
            print(f"DB Select 1: {res.scalar()}")
    except Exception as e:
        print(f"DB Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
