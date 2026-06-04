import asyncio
from datetime import datetime, timezone

from app.config import settings
from app.database import async_session_factory
from app.core.logging import logger


class MonitoringWorker:
    def __init__(self, pnl_interval: int = 300, drift_interval: int = 120, health_interval: int = 60):
        self.pnl_interval = pnl_interval
        self.drift_interval = drift_interval
        self.health_interval = health_interval
        self._running = False

    async def run(self):
        self._running = True
        logger.info("monitoring_worker_started", pnl_interval=self.pnl_interval, drift_interval=self.drift_interval)

        last_pnl = 0
        last_drift = 0
        last_health = 0

        while self._running:
            now = asyncio.get_event_loop().time()

            if now - last_pnl >= self.pnl_interval:
                await self._recompute_pnl()
                last_pnl = now

            if now - last_drift >= self.drift_interval:
                await self._scan_drift()
                last_drift = now

            if now - last_health >= self.health_interval:
                await self._check_health()
                last_health = now

            await asyncio.sleep(10)

    async def _recompute_pnl(self):
        try:
            async with async_session_factory() as db:
                from app.services.monitoring.pnl_service import PnLService
                svc = PnLService(db)
                pnl = await svc.get_portfolio_pnl()
                logger.info("monitoring_pnl_snapshot", realized=pnl["total_realized_pnl"], unrealized=pnl["total_unrealized_pnl"])
        except Exception as e:
            logger.warning("monitoring_pnl_error", error=str(e))

    async def _scan_drift(self):
        try:
            async with async_session_factory() as db:
                from app.services.monitoring.drift_service import DriftDetectionService
                svc = DriftDetectionService(db)
                order_drifts = await svc.scan_all_active_orders()
                position_drifts = await svc.scan_all_open_positions()

                if order_drifts:
                    logger.warning("monitoring_drift_detected", order_drifts=len(order_drifts))
                if position_drifts:
                    logger.warning("monitoring_position_drift", position_drifts=len(position_drifts))
        except Exception as e:
            logger.warning("monitoring_drift_scan_error", error=str(e))

    async def _check_health(self):
        try:
            async with async_session_factory() as db:
                from app.services.monitoring.order_state_service import OrderStateService
                svc = OrderStateService(db)
                active = await svc.get_active_orders()
                stuck = [o for o in active if o.status != "pending" and o.status not in ("filled", "cancelled", "failed")]

                if len(stuck) > 5:
                    logger.warning("monitoring_high_active_orders", count=len(stuck), max_stuck=5)

                logger.info("monitoring_health", active_orders=len(active), stuck_orders=len(stuck))
        except Exception as e:
            logger.warning("monitoring_health_error", error=str(e))

    async def run_single_cycle(self):
        try:
            await self._recompute_pnl()
        except Exception:
            pass
        try:
            await self._scan_drift()
        except Exception:
            pass
        try:
            await self._check_health()
        except Exception:
            pass

    async def stop(self):
        self._running = False
