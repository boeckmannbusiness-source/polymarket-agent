from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "echo": settings.APP_DEBUG,
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW
    engine_kwargs["connect_args"] = {
        "timeout": 10,
        "command_timeout": 30,
        "server_settings": {"statement_timeout": "15000"},
        "statement_cache_size": 0
    }

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
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
    try:
        await engine.dispose()
    except Exception:
        pass
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # mode transitions table (created by metadata but ensure index)
        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_system_mode_transitions_created_at
                ON system_mode_transitions(created_at)
            """))
        except Exception:
            pass
        await conn.execute(text("""
            ALTER TABLE backtest_runs
            ADD COLUMN IF NOT EXISTS sortino_ratio NUMERIC(12, 6),
            ADD COLUMN IF NOT EXISTS calmar_ratio NUMERIC(12, 6),
            ADD COLUMN IF NOT EXISTS total_pnl NUMERIC(24, 8),
            ADD COLUMN IF NOT EXISTS mode VARCHAR(32),
            ADD COLUMN IF NOT EXISTS error_message TEXT
        """))
        for table, col in [("trades", "correlation_id"), ("agent_logs", "correlation_id"),
                           ("execution_traces", "correlation_id"), ("signals", "correlation_id")]:
            try:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} UUID"))
                await conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_{col} ON {table}({col})"))
            except Exception:
                pass
