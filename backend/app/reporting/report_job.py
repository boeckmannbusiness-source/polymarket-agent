import json
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.core.logging import logger
from app.llm import get_llm_provider
from app.reporting.prompt import TELEGRAM_SYSTEM_PROMPT, EMAIL_SYSTEM_PROMPT, build_user_prompt
from app.reporting.telegram import TelegramReporter
from app.reporting.email import EmailReporter
from app.reporting.config import get_report_config


class AgentReportJob:
    def __init__(self):
        self._llm = get_llm_provider()
        self._telegram = TelegramReporter()
        self._email = EmailReporter()
        self._snapshot_url = f"http://localhost:{settings.APP_PORT}/api/v1/agent/snapshot"

    async def fetch_snapshot(self) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self._snapshot_url)
            resp.raise_for_status()
            return resp.json()

    async def run_telegram_report(self):
        logger.info("report_job_telegram_start")
        try:
            snapshot = await self.fetch_snapshot()
            prompt = build_user_prompt(snapshot, mode="telegram")
            response = await self._llm.generate(
                prompt=prompt,
                system=TELEGRAM_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=1024,
            )
            await self._telegram.send_summary(response.content)
            logger.info("report_job_telegram_done")
        except Exception as e:
            logger.error("report_job_telegram_failed", error=str(e))

    async def run_email_report(self):
        logger.info("report_job_email_start")
        try:
            snapshot = await self.fetch_snapshot()
            prompt = build_user_prompt(snapshot, mode="email")
            response = await self._llm.generate(
                prompt=prompt,
                system=EMAIL_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=2048,
            )
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            await self._email.send_report(
                subject=f"Polymarket Daily Trading Report - {today}",
                body=response.content,
            )
            logger.info("report_job_email_done")
        except Exception as e:
            logger.error("report_job_email_failed", error=str(e))

    async def run_alert_check(self, snapshot: dict):
        cfg = get_report_config()
        portfolio = snapshot.get("portfolio", {})
        risk = snapshot.get("risk", {})

        pnl_24h = portfolio.get("pnl_24h", 0)
        risk_level = risk.get("risk_level", "low")

        triggered = False
        if isinstance(pnl_24h, (int, float)) and pnl_24h < cfg.alert_pnl_drop_threshold:
            await self._telegram.send_summary(
                f"\u26a0\ufe0f *Alert: PnL Drop*\n24h PnL at {pnl_24h:+.2f} (threshold {cfg.alert_pnl_drop_threshold:+.2f})"
            )
            triggered = True

        if cfg.alert_risk_high_push and risk_level == "high":
            alerts = risk.get("active_risk_alerts", [])
            alert_text = "\n".join(f"\u2022 {a}" for a in alerts[:5]) if alerts else "no details"
            await self._telegram.send_summary(
                f"\U0001f534 *Alert: Risk Level HIGH*\n{alert_text}"
            )
            triggered = True

        if triggered:
            logger.info("report_job_alert_triggered", pnl_24h=pnl_24h, risk_level=risk_level)
