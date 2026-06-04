from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExchangeOrder
from app.services.execution.reconciliation_service import ReconciliationService
from app.services.incidents.incident_service import incident_service
from app.services.audit.audit_logger import emit
from app.core.logging import logger
from app.core.metrics import recovery_scans_total, recovered_orders_total, abandoned_orders_total

RECOVERY_LAST_SCAN_KEY = "recovery:last_scan"
ABANDONED_KEY = "recovery:abandoned:orders"
MAX_RETRY_THRESHOLD = 3
DEFAULT_RECOVERY_WINDOW_MINUTES = 60


class OrderRecoveryService:
    def __init__(self, db: AsyncSession, reconciliation_svc: ReconciliationService | None = None):
        self.db = db
        self._reconciliation = reconciliation_svc

    async def _get_reconciliation(self) -> ReconciliationService:
        if self._reconciliation is None:
            self._reconciliation = ReconciliationService(self.db)
        return self._reconciliation

    async def run_scan(self, recovery_window_minutes: int = DEFAULT_RECOVERY_WINDOW_MINUTES, force: bool = False) -> dict:
        r = await self._safe_redis()
        if not force and r is not None:
            try:
                last_scan = await r.get(RECOVERY_LAST_SCAN_KEY)
                if last_scan:
                    last_dt = datetime.fromisoformat(last_scan.decode() if isinstance(last_scan, bytes) else last_scan)
                    if datetime.now(timezone.utc) - last_dt < timedelta(minutes=5):
                        return {"orders_scanned": 0, "orders_recovered": 0, "incidents_created": 0, "abandoned_orders": 0, "skipped": "recent_scan_exists"}
            except Exception:
                pass

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=recovery_window_minutes)

        result = await self.db.execute(
            select(ExchangeOrder).where(
                ExchangeOrder.status.in_(["pending", "submitted", "partially_filled"]),
            )
        )
        orders = list(result.scalars().all())
        scanned = len(orders)
        recovered = 0
        incidents_created = 0
        abandoned = 0

        for order in orders:
            if order.retry_count and order.retry_count >= MAX_RETRY_THRESHOLD:
                await self._mark_abandoned(order)
                abandoned += 1
                continue

            if order.submitted_at and order.submitted_at >= cutoff:
                continue

            if order.engine_type == "live" and order.clob_order_id:
                success = await self._reconcile_live_order(order)
                if success:
                    recovered += 1
                else:
                    await self._create_recovery_incident(order, "exchange_reconciliation_failed")
                    incidents_created += 1
            elif order.status == "pending":
                if (order.submitted_at or order.created_at) and (order.submitted_at or order.created_at) < cutoff - timedelta(minutes=30):
                    await self._mark_abandoned(order)
                    abandoned += 1
                else:
                    incidents_created += 1

        if r is not None:
            try:
                await r.set(RECOVERY_LAST_SCAN_KEY, datetime.now(timezone.utc).isoformat())
            except Exception:
                pass

        recovery_scans_total.inc()
        if recovered:
            recovered_orders_total.inc(recovered)
        if abandoned:
            abandoned_orders_total.inc(abandoned)

        logger.info(
            "order_recovery_scan_complete",
            scanned=scanned,
            recovered=recovered,
            incidents=incidents_created,
            abandoned=abandoned,
        )

        return {
            "orders_scanned": scanned,
            "orders_recovered": recovered,
            "incidents_created": incidents_created,
            "abandoned_orders": abandoned,
        }

    async def _reconcile_live_order(self, order: ExchangeOrder) -> bool:
        try:
            svc = await self._get_reconciliation()
            await svc.reconcile_order(order)
            await self.db.flush()
            await emit("order.recovered", "exchange_order", str(order.id), {
                "trade_id": str(order.trade_id),
                "clob_order_id": order.clob_order_id,
            })
            return True
        except Exception as e:
            logger.warning("recovery_reconcile_failed", order_id=str(order.id), error=str(e))
            return False

    async def _mark_abandoned(self, order: ExchangeOrder):
        order.status = "cancelled"
        order.last_error = "abandoned_by_recovery"
        await self.db.flush()
        r = await self._safe_redis()
        if r is not None:
            try:
                await r.sadd(ABANDONED_KEY, str(order.id))
            except Exception:
                pass
        await emit("order.abandoned", "exchange_order", str(order.id), {
            "trade_id": str(order.trade_id),
            "status": order.status,
            "retry_count": order.retry_count,
        })
        logger.warning("order_abandoned", order_id=str(order.id), trade_id=str(order.trade_id))

    async def _create_recovery_incident(self, order: ExchangeOrder, reason: str):
        try:
            await incident_service.create_from_alert({
                "title": f"Order recovery failed: {str(order.id)[:8]}",
                "severity": "warning",
                "message": f"Order {order.id} unrecoverable: {reason}",
                "entity_type": "exchange_order",
                "entity_id": str(order.id),
            })
        except Exception as e:
            logger.error("recovery_incident_failed", order_id=str(order.id), error=str(e))

    async def _safe_redis(self):
        try:
            from app.redis import get_redis
            return await get_redis()
        except Exception:
            return None
