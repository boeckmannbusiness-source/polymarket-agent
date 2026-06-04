import pytest
from unittest.mock import AsyncMock, patch, PropertyMock

from app.services.scheduler.task_scheduler import TaskScheduler


class TestTaskScheduler:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.scheduler = TaskScheduler()
        self.counter = 0

    async def test_register_job(self):
        callback = AsyncMock()
        await self.scheduler.register_job("test_job", 3600, callback, enabled=True)
        jobs = await self.scheduler.get_all_jobs()
        names = [j.get("name") for j in jobs]
        assert "test_job" in names

    async def test_disable_job(self):
        callback = AsyncMock()
        await self.scheduler.register_job("disable_test", 3600, callback, enabled=True)
        await self.scheduler.disable_job("disable_test")
        job = await self.scheduler.get_job("disable_test")
        assert job is not None

    async def test_enable_job(self):
        callback = AsyncMock()
        await self.scheduler.register_job("enable_test", 3600, callback, enabled=False)
        job_before = await self.scheduler.get_job("enable_test")
        await self.scheduler.enable_job("enable_test")
        job_after = await self.scheduler.get_job("enable_test")
        assert job_after is not None

    async def test_get_job_nonexistent(self):
        job = await self.scheduler.get_job("nonexistent")
        assert job is None

    async def test_get_history_empty(self):
        history = await self.scheduler.get_history("test_job")
        assert history == []

    async def test_run_job_calls_callback(self):
        async def inc_counter():
            self.counter += 1

        with patch.object(self.scheduler, "_safe_redis", return_value=None):
            await self.scheduler.register_job("counter_job", 60, inc_counter, enabled=True)

        assert self.scheduler._callbacks["counter_job"] is inc_counter
