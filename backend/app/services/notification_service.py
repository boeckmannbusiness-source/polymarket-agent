from app.config import settings
from app.core.logging import logger


class NotificationService:
    def __init__(self):
        self.alert_levels = {"debug": 0, "info": 1, "warning": 2, "critical": 3}
        self.min_level = self.alert_levels.get(settings.TELEGRAM_ALERT_LEVEL, 1)

    async def send_alert(self, message: str, level: str = "info"):
        if self.alert_levels.get(level, 0) < self.min_level:
            return

        logger.info("alert", level=level, message=message)

        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            await self._send_telegram(message)

    async def _send_telegram(self, message: str):
        try:
            from telegram import Bot

            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            await bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")
        except Exception as e:
            logger.error("telegram_send_failed", error=str(e))

    async def format_whale_alert(self, wallet_address: str, market_title: str, side: str, size: float, outcome: str) -> str:
        return (
            f"\U0001f535 *Whale Alert*\n"
            f"Wallet `{wallet_address[:8]}...` {side} {size:.2f} shares of *{outcome}*\n"
            f"Market: {market_title}"
        )

    async def format_signal_alert(self, signal_type: str, direction: str, confidence: float, market_title: str, reasoning: str) -> str:
        emoji = "\U0001f7e2" if direction == "bullish" else "\U0001f534"
        return (
            f"{emoji} *Signal: {confidence:.0%} confidence {direction}*\n"
            f"Type: {signal_type}\n"
            f"Market: {market_title}\n"
            f"Reason: {reasoning}"
        )

    async def format_trade_alert(self, trade_type: str, side: str, size: float, price: float, market_title: str, status: str) -> str:
        return (
            f"\U0001f7e1 *Trade {status}*\n"
            f"{trade_type.upper()} {side.upper()} {size:.2f} @ {price:.4f}\n"
            f"Market: {market_title}"
        )

    async def format_risk_alert(self, reason: str) -> str:
        return f"\U0001f534 *Risk Blocked*\n{reason}"

    async def format_pnl_alert(self, pnl: float, pnl_percent: float, market_title: str) -> str:
        emoji = "\U0001f7e2" if pnl > 0 else "\U0001f534"
        return f"{emoji} *Position Closed*: {pnl:+.2f} ({pnl_percent:+.2%}) on {market_title}"
