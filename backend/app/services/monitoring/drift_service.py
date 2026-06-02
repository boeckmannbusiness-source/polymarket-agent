from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExchangeOrder, Fill, Position
from app.core.logging import logger


DRIFT_ALERT_STUCK_MINUTES = 30
DRIFT_ALERT_MIN_FILL_RATE = 50.0
DRIFT_ALERT_MAX_RETRIES = 3


class DriftDetectionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect_order_drift(self, exchange_order: ExchangeOrder, clob_state: dict | None = None) -> dict[str, Any]:
        drift_report: dict[str, Any] = {
            "order_id": str(exchange_order.id),
            "drift_detected": False,
            "issues": [],
        }

        if clob_state:
            clob_status = clob_state.get("status", "").lower()
            if clob_status and clob_status != exchange_order.status:
                drift_report["issues"].append({
                    "type": "status_mismatch",
                    "db": exchange_order.status,
                    "clob": clob_status,
                })

            clob_filled = float(clob_state.get("filledSize", 0) or 0)
            db_filled = float(exchange_order.filled_size) if exchange_order.filled_size else 0.0
            if abs(clob_filled - db_filled) > 0.0001:
                drift_report["issues"].append({
                    "type": "size_mismatch",
                    "db_filled": db_filled,
                    "clob_filled": clob_filled,
                    "delta": clob_filled - db_filled,
                })

        if exchange_order.status in ("submitted", "partially_filled"):
            if exchange_order.submitted_at:
                elapsed = (datetime.now(timezone.utc) - exchange_order.submitted_at).total_seconds() / 60
                if elapsed > DRIFT_ALERT_STUCK_MINUTES:
                    drift_report["issues"].append({
                        "type": "order_stuck",
                        "submitted_minutes_ago": round(elapsed, 1),
                        "threshold_minutes": DRIFT_ALERT_STUCK_MINUTES,
                    })

        if exchange_order.retry_count >= DRIFT_ALERT_MAX_RETRIES:
            drift_report["issues"].append({
                "type": "retry_count_spike",
                "retry_count": exchange_order.retry_count,
                "threshold": DRIFT_ALERT_MAX_RETRIES,
            })

        if exchange_order.size and exchange_order.filled_size:
            fill_rate = float(exchange_order.filled_size) / float(exchange_order.size) * 100
            if exchange_order.status == "filled" and fill_rate < DRIFT_ALERT_MIN_FILL_RATE:
                drift_report["issues"].append({
                    "type": "low_fill_rate",
                    "fill_rate_pct": round(fill_rate, 2),
                    "threshold_pct": DRIFT_ALERT_MIN_FILL_RATE,
                })

        if drift_report["issues"]:
            drift_report["drift_detected"] = True

        return drift_report

    async def detect_position_drift(self, position: Position) -> dict[str, Any]:
        drift_report: dict[str, Any] = {
            "position_id": str(position.id),
            "drift_detected": False,
            "issues": [],
        }

        if position.market_id:
            result = await self.db.execute(
                select(Fill).where(Fill.market_id == position.market_id)
            )
            fills = list(result.scalars().all())

            fill_buy_size = sum(float(f.size) for f in fills if f.side == "buy")
            fill_sell_size = sum(float(f.size) for f in fills if f.side == "sell")
            fill_net_size = fill_buy_size - fill_sell_size

            db_pos_size = float(position.size)
            if abs(fill_net_size - db_pos_size) > 0.001:
                drift_report["issues"].append({
                    "type": "position_size_mismatch",
                    "fill_derived_net": round(fill_net_size, 8),
                    "cached_position_size": round(db_pos_size, 8),
                    "delta": round(fill_net_size - db_pos_size, 8),
                })

        if drift_report["issues"]:
            drift_report["drift_detected"] = True

        return drift_report

    async def scan_all_active_orders(self) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(ExchangeOrder).where(
                ExchangeOrder.status.in_(["pending", "submitted", "partially_filled"])
            )
        )
        orders = list(result.scalars().all())
        reports = []
        for order in orders:
            report = await self.detect_order_drift(order)
            if report["drift_detected"]:
                reports.append(report)
        return reports

    async def scan_all_open_positions(self) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(Position).where(Position.status == "OPEN")
        )
        positions = list(result.scalars().all())
        reports = []
        for pos in positions:
            report = await self.detect_position_drift(pos)
            if report["drift_detected"]:
                reports.append(report)
        return reports
