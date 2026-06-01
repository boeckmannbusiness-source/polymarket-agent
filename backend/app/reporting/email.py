import asyncio
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone

from app.config import settings
from app.core.logging import logger


class EmailReporter:
    async def send_report(self, subject: str, body: str):
        if not settings.SMTP_HOST or not settings.SMTP_FROM or not settings.REPORT_EMAIL_TO:
            logger.warning("email_not_configured_skipping")
            return

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = settings.REPORT_EMAIL_TO
        msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._send_sync, msg)
            logger.info("email_report_sent", to=settings.REPORT_EMAIL_TO, subject=subject)
        except Exception as e:
            logger.error("email_send_failed", error=str(e))

    def _send_sync(self, msg: MIMEText):
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
