"""Create all core tables from SQLAlchemy models on Supabase."""

import asyncio
from app.database import engine, Base
from app.models import *


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("All core tables created successfully")


if __name__ == "__main__":
    asyncio.run(main())
