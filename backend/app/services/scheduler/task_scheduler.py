import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable

from app.core.logging import logger
from app.core.metrics import scheduler_job_failures_total, scheduler_execution_duration
from app.services.audit.audit_logger import emit
from app.services.incidents.incident_service import incident_service

SCHEDULER_JOBS_PREFIX = "scheduler:jobs"
SCHEDULER_HISTORY_PREFIX = "scheduler:history"
MAX_RETRIES_BEFORE_INCIDENT = 5


class TaskScheduler:
    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._callbacks: dict[str, Callable] = {}

    async def register_job(self, name: str, interval: int, callback: Callable, enabled: bool = True):
        self._callbacks[name] = callback
        r = await self._safe_redis()
        if r is not None:
            try:
                await r.hset(f"{SCHEDULER_JOBS_PREFIX}:{name}", mapping={
                    "interval": str(interval),
                    "enabled": "1" if enabled else "0",
                    "retry_count": "0",
                    "last_run": "",
                })
            except Exception:
                pass
        task = asyncio.create_task(self._run_job(name, interval, callback), name=f"scheduler_{name}")
        self._tasks[name] = task
        logger.info("scheduler_job_registered", name=name, interval=interval)

    async def disable_job(self, name: str):
        r = await self._safe_redis()
        if r is not None:
            try:
                await r.hset(f"{SCHEDULER_JOBS_PREFIX}:{name}", "enabled", "0")
            except Exception:
                pass
        logger.info("scheduler_job_disabled", name=name)

    async def enable_job(self, name: str):
        r = await self._safe_redis()
        if r is not None:
            try:
                await r.hset(f"{SCHEDULER_JOBS_PREFIX}:{name}", "enabled", "1")
            except Exception:
                pass
        logger.info("scheduler_job_enabled", name=name)

    async def get_job(self, name: str) -> dict[str, Any] | None:
        r = await self._safe_redis()
        if r is not None:
            try:
                raw = await r.hgetall(f"{SCHEDULER_JOBS_PREFIX}:{name}")
                if raw:
                    result = {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in raw.items()}
                    result["name"] = name
                    return result
            except Exception:
                pass
        if name in self._callbacks:
            return {"name": name, "enabled": "1", "interval": "0", "retry_count": "0", "last_run": ""}
        return None

    async def get_all_jobs(self) -> list[dict[str, Any]]:
        jobs = []
        for name in self._callbacks:
            job = await self.get_job(name)
            if job:
                jobs.append(job)
        return jobs

    async def get_history(self, name: str, limit: int = 20) -> list[dict[str, Any]]:
        r = await self._safe_redis()
        if r is None:
            return []
        try:
            raw = await r.xrevrange(f"{SCHEDULER_HISTORY_PREFIX}:{name}", count=limit)
            results = []
            for msg_id, fields in raw:
                entry = dict(fields)
                entry["msg_id"] = msg_id
                results.append(entry)
            return results
        except Exception:
            return []

    async def _run_job(self, name: str, interval: int, callback: Callable):
        await asyncio.sleep(30)
        while True:
            try:
                r = await self._safe_redis()
                if r is not None:
                    try:
                        enabled = await r.hget(f"{SCHEDULER_JOBS_PREFIX}:{name}", "enabled")
                        if enabled == b"0":
                            await asyncio.sleep(interval)
                            continue
                    except Exception:
                        pass

                t0 = time.monotonic()
                await callback()
                duration = time.monotonic() - t0

                scheduler_execution_duration.labels(job_name=name).observe(duration)
                await self._record_execution(name, "success", duration)
                if r is not None:
                    try:
                        await r.hset(f"{SCHEDULER_JOBS_PREFIX}:{name}", mapping={
                            "last_run": datetime.now(timezone.utc).isoformat(),
                            "retry_count": "0",
                        })
                    except Exception:
                        pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self._record_execution(name, "failed", 0, str(e))
                await self._increment_retry(name, str(e))

            await asyncio.sleep(interval)

    async def _record_execution(self, name: str, status: str, duration: float, error: str = ""):
        record = {
            "name": name,
            "status": status,
            "duration_ms": str(int(duration * 1000)),
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        r = await self._safe_redis()
        if r is not None:
            try:
                await r.xadd(f"{SCHEDULER_HISTORY_PREFIX}:{name}", record, maxlen=1000, approximate=True)
            except Exception:
                pass

    async def _increment_retry(self, name: str, error: str):
        r = await self._safe_redis()
        retry_count = 0
        if r is not None:
            try:
                raw = await r.hget(f"{SCHEDULER_JOBS_PREFIX}:{name}", "retry_count")
                retry_count = (int(raw) if raw else 0) + 1
                await r.hset(f"{SCHEDULER_JOBS_PREFIX}:{name}", "retry_count", str(retry_count))
            except Exception:
                pass

        scheduler_job_failures_total.labels(job_name=name).inc()

        await emit("scheduler.job_failed", "scheduler", name, {
            "error": error,
            "retry_count": retry_count,
        })

        if retry_count >= MAX_RETRIES_BEFORE_INCIDENT:
            try:
                await incident_service.create_from_alert({
                    "title": f"Scheduler job failing: {name}",
                    "severity": "warning",
                    "message": f"Job '{name}' failed {retry_count} times. Last error: {error}",
                })
            except Exception:
                pass

    async def shutdown(self):
        for name, task in self._tasks.items():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    async def _safe_redis(self):
        try:
            from app.redis import get_redis
            return await get_redis()
        except Exception:
            return None


scheduler = TaskScheduler()
