import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager

from app.services.shadow.runtime_scheduler import ShadowRuntimeScheduler
from app.models.shadow_runtime_state import ShadowRuntimeState

@pytest.mark.asyncio
async def test_scheduler_recovery(db_session: AsyncSession):
    # Mock session factory
    @asynccontextmanager
    async def session_factory():
        yield db_session

    # Initial run
    scheduler = ShadowRuntimeScheduler(session_factory)
    await scheduler._recover_state()
    assert scheduler.generation == 1

    # Simulate some state
    state = (await db_session.execute(select(ShadowRuntimeState))).scalar_one()
    state.scheduler_generation = 5
    await db_session.commit()

    # Restart
    new_scheduler = ShadowRuntimeScheduler(session_factory)
    await new_scheduler._recover_state()
    assert new_scheduler.generation == 6
    assert new_scheduler.recovery_events == 1

@pytest.mark.asyncio
async def test_scheduler_metrics_report(db_session: AsyncSession):
    @asynccontextmanager
    async def session_factory():
        yield db_session

    scheduler = ShadowRuntimeScheduler(session_factory)
    await scheduler._recover_state()
    await scheduler._step() # this calls _report_metrics

    import os
    assert os.path.exists("SHADOW_RUNTIME_REPORT.md")
    with open("SHADOW_RUNTIME_REPORT.md", "r") as f:
        content = f.read()
        assert "SHADOW_RUNTIME_REPORT" in content
        assert "decisions/hour" in content
