from app.core.logging import logger
from app.services.notification_service import NotificationService


class TelegramReporter:
    def __init__(self):
        self._notifier = NotificationService()

    async def send_summary(self, text: str):
        if len(text) > 4000:
            text = text[:3997] + "..."

        await self._notifier.send_alert(
            message=text,
            level="info",
        )

        logger.info(
            "telegram_report_sent",
            length=len(text),
        )
