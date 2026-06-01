import asyncio
from datetime import datetime, timezone, timedelta

from app.core.logging import logger
from app.reporting.report_job import AgentReportJob
from app.reporting.config import get_report_config


class ReportScheduler:
    def __init__(self):
        self._job = AgentReportJob()
        self._running = False
        self._last_telegram_run: datetime | None = None
        self._last_email_date: str | None = None

    async def _telegram_due(self, cfg) -> bool:
        if self._last_telegram_run is None:
            return True
        elapsed = datetime.now(timezone.utc) - self._last_telegram_run
        return elapsed >= timedelta(hours=cfg.telegram_interval_hours)

    async def _email_due(self, cfg) -> bool:
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        if self._last_email_date == today:
            return False
        if now.hour < cfg.email_hour or (now.hour == cfg.email_hour and now.minute < cfg.email_minute):
            return False
        return True

    async def run_loop(self):
        if self._running:
            logger.warning("report_scheduler_already_running")
            return
        self._running = True
        cfg = get_report_config()
        logger.info(
            "report_scheduler_started",
            telegram_interval_h=cfg.telegram_interval_hours,
            email_time=f"{cfg.email_hour:02d}:{cfg.email_minute:02d}",
        )

        try:
            while self._running:
                try:
                    if await self._telegram_due(cfg):
                        logger.info("scheduler_trigger_telegram")
                        await self._job.run_telegram_report()
                        self._last_telegram_run = datetime.now(timezone.utc)

                    if await self._email_due(cfg):
                        logger.info("scheduler_trigger_email")
                        await self._job.run_email_report()
                        self._last_email_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                    try:
                        snapshot = await self._job.fetch_snapshot()
                        await self._job.run_alert_check(snapshot)
                    except Exception:
                        pass
                except Exception as e:
                    logger.error("report_scheduler_iteration_error", error=str(e))

                await asyncio.sleep(300)
        except asyncio.CancelledError:
            logger.info("report_scheduler_cancelled")
        finally:
            self._running = False

    def stop(self):
        self._running = False
