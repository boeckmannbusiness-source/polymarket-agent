from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"timeout": 10, "command_timeout": 30},
    echo=settings.APP_DEBUG,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("""
            ALTER TABLE backtest_runs
            ADD COLUMN IF NOT EXISTS sortino_ratio NUMERIC(12, 6),
            ADD COLUMN IF NOT EXISTS calmar_ratio NUMERIC(12, 6),
            ADD COLUMN IF NOT EXISTS total_pnl NUMERIC(24, 8),
            ADD COLUMN IF NOT EXISTS mode VARCHAR(32),
            ADD COLUMN IF NOT EXISTS error_message TEXT
        """))
