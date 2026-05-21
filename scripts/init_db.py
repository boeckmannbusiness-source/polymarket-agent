"""Initialize database schema."""
import asyncio

from app.database import init_db, engine
from app.core.logging import setup_logging, logger


async def main():
    setup_logging()
    logger.info("initializing_database")
    await init_db()
    await engine.dispose()
    logger.info("database_initialized")


if __name__ == "__main__":
    asyncio.run(main())
