import asyncio
from datetime import datetime, timezone, timedelta

from app.agents.base import BaseAgent
from app.core.events import EventBus
from app.core.logging import logger
from app.database import async_session_factory
from app.models import Trade, AgentLog


class MonitoringAgent(BaseAgent):
    name = "monitoring_agent"

    def __init__(self):
        super().__init__()
        self.metrics = {
            "total_signals": 0,
            "total_trades": 0,
            "approved_trades": 0,
            "rejected_trades": 0,
            "failed_trades": 0,
            "open_positions": 0,
            "total_pnl": 0.0,
            "last_heartbeat": None,
        }

    async def setup(self):
        logger.info("monitoring_agent_setup")

    async def loop(self):
        while self.running:
            try:
                await self.collect_metrics()
                await self.report_status()

                r = await EventBus.subscribe_to_stream("agent:event", "monitoring_agent", "mon_1")
                messages = await EventBus.read_stream(r, "agent:event", "monitoring_agent", "mon_1", block=5000)

                for msg in messages:
                    await self.process_event(msg)
                    if msg.get("stream") == "agent:event":
                        await EventBus.ack_message(r, "agent:event", "monitoring_agent", msg["id"])

            except Exception as e:
                logger.error("monitoring_agent_error", error=str(e))

            await asyncio.sleep(10)

    async def collect_metrics(self):
        async with async_session_factory() as db:
            from sqlalchemy import select, func, and_

            total_trades = await db.execute(select(func.count(Trade.id)))
            self.metrics["total_trades"] = total_trades.scalar() or 0

            open_positions = await db.execute(
                select(func.count(Trade.id)).where(Trade.status.in_(["open", "pending"]))
            )
            self.metrics["open_positions"] = open_positions.scalar() or 0

            total_pnl = await db.execute(
                select(func.coalesce(func.sum(Trade.pnl), 0)).where(Trade.status == "closed")
            )
            self.metrics["total_pnl"] = float(total_pnl.scalar() or 0)

    async def process_event(self, msg: dict):
        data = msg.get("data", {})
        event_type = msg.get("event_type", "")

        if event_type == "signal.generated":
            self.metrics["total_signals"] += 1
        elif event_type == "trade.risk_approved":
            self.metrics["approved_trades"] += 1
        elif event_type == "trade.risk_rejected":
            self.metrics["rejected_trades"] += 1
        elif event_type == "trade.failed":
            self.metrics["failed_trades"] += 1
        elif event_type == "agent.health":
            self.metrics["last_heartbeat"] = datetime.now(timezone.utc).isoformat()

    async def report_status(self):
        self.metrics["last_heartbeat"] = datetime.now(timezone.utc).isoformat()

        await EventBus.publish(
            "system:alert",
            "system.health_check",
            self.name,
            self.metrics,
        )

        status = (
            f"📊 *System Status*\n"
            f"Signals: {self.metrics['total_signals']} | Trades: {self.metrics['total_trades']}\n"
            f"Open: {self.metrics['open_positions']} | PnL: {self.metrics['total_pnl']:+.2f}\n"
            f"Approved: {self.metrics['approved_trades']} | Rejected: {self.metrics['rejected_trades']} | Failed: {self.metrics['failed_trades']}"
        )
        logger.info("system_status", metrics=self.metrics)
