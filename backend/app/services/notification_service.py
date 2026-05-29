import asyncio
from collections import deque

from app.config import settings
from app.core.logging import logger
from app.core.metrics import telegram_send_failures_total


class RateLimiter:
    def __init__(self, max_per_minute: int = 30):
        self._max = max_per_minute
        self._timestamps: deque[float] = deque(maxlen=max_per_minute)

    async def allow(self) -> bool:
        now = asyncio.get_event_loop().time()
        while self._timestamps and now - self._timestamps[0] > 60:
            self._timestamps.popleft()
        if len(self._timestamps) >= self._max:
            return False
        self._timestamps.append(now)
        return True


class NotificationService:
    def __init__(self):
        self._bot = None
        self._rate_limiter = RateLimiter(max_per_minute=30)
        self._buffer: deque[tuple[str, str]] = deque(maxlen=100)
        self._alert_levels = {"debug": 0, "info": 1, "warning": 2, "critical": 3}
        self._min_level = self._alert_levels.get(settings.TELEGRAM_ALERT_LEVEL, 1)

    async def _ensure_bot(self):
        if self._bot is None and settings.TELEGRAM_BOT_TOKEN:
            from telegram import Bot
            self._bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    async def send_alert(self, message: str, level: str = "info"):
        if self._alert_levels.get(level, 0) < self._min_level:
            return

        logger.info("alert", level=level, message=message)

        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            return

        if not await self._rate_limiter.allow():
            self._buffer.append((message, level))
            return

        await self._send_telegram(message)

    async def _send_telegram(self, message: str):
        await self._ensure_bot()
        if self._bot is None:
            return
        for attempt in range(2):
            try:
                await self._bot.send_message(
                    chat_id=settings.TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode="Markdown",
                )
                return
            except Exception as e:
                if attempt == 0:
                    await asyncio.sleep(1)
                else:
                    telegram_send_failures_total.inc()
                    logger.error("telegram_send_failed", error=str(e))
                    self._buffer.append((message, "critical"))

    async def flush_buffer(self):
        while self._buffer:
            msg, level = self._buffer.popleft()
            await self.send_alert(msg, level=level)

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
