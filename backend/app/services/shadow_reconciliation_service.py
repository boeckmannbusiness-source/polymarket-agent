import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.metrics import solana_shadow_reconciliation_drift_total
from app.models.shadow_position import ShadowPosition


_RECONCILE_EPSILON = 0.01


def _recompute_pnl(entry_price: float, exit_price: float, size_usd: float) -> tuple[float, float]:
    quantity = size_usd / entry_price if entry_price > 0 else 0.0
    gross = (exit_price - entry_price) * quantity
    entry_fee = size_usd * settings.SOLANA_SHADOW_FEE_PCT
    exit_fee = size_usd * settings.SOLANA_SHADOW_FEE_PCT
    net = gross - entry_fee - exit_fee
    return round(gross, 2), round(net, 2)


_SHADOW_FIELDS = [
    ShadowPosition.entry_price,
    ShadowPosition.exit_price,
    ShadowPosition.size_usd,
    ShadowPosition.net_pnl_usd,
    ShadowPosition.gross_pnl_usd,
    ShadowPosition.status,
    ShadowPosition.strategy,
]


class ShadowReconciliationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def reconcile_all(self) -> dict:
        result = await self.db.execute(
            select(*_SHADOW_FIELDS)
            .where(ShadowPosition.status == "closed")
            .where(ShadowPosition.net_pnl_usd.isnot(None)),
        )
        rows = result.all()

        drift_count = 0
        critical_count = 0
        anomalies: list[dict] = []

        for row in rows:
            ep = row.entry_price
            xp = row.exit_price
            sz = row.size_usd
            stored_net = float(row.net_pnl_usd) if row.net_pnl_usd is not None else 0.0
            status = self._validate_position(row)
            if status is not None:
                drift_count += 1
                anomalies.append(status)
                severity = "critical" if abs(status["diff_pct"]) > 5.0 else "warning"
                if severity == "critical":
                    critical_count += 1
                solana_shadow_reconciliation_drift_total.labels(
                    strategy=row.strategy, severity=severity,
                ).inc()
                continue

            recomputed_gross, recomputed_net = _recompute_pnl(
                float(ep), float(xp), float(sz),
            )
            diff = abs(recomputed_net - stored_net)
            if diff > _RECONCILE_EPSILON:
                drift_count += 1
                entry = {
                    "strategy": row.strategy,
                    "stored_net": stored_net,
                    "recomputed_net": recomputed_net,
                    "diff": round(diff, 2),
                    "diff_pct": round(diff / abs(stored_net) * 100 if stored_net else 0.0, 2),
                }
                severity = "critical" if abs(entry["diff_pct"]) > 5.0 else "warning"
                if severity == "critical":
                    critical_count += 1
                entry["severity"] = severity
                anomalies.append(entry)
                solana_shadow_reconciliation_drift_total.labels(
                    strategy=row.strategy, severity=severity,
                ).inc()

        return {
            "total_reconciled": len(rows),
            "drift_count": drift_count,
            "critical_count": critical_count,
            "anomalies": anomalies,
        }

    def _validate_position(self, row) -> dict | None:
        issues = []
        if row.entry_price is None or float(row.entry_price) <= 0:
            issues.append("entry_price_missing_or_zero")
        if row.status == "closed" and row.exit_price is None:
            issues.append("exit_price_missing_for_closed")
        if row.size_usd is None or float(row.size_usd) <= 0:
            issues.append("size_usd_missing_or_zero")
        if row.net_pnl_usd is None:
            issues.append("net_pnl_missing_for_closed")
        if not issues:
            return None
        return {
            "strategy": row.strategy,
            "issues": issues,
            "stored_net": float(row.net_pnl_usd) if row.net_pnl_usd is not None else None,
            "diff": 0.0,
            "diff_pct": 0.0,
        }

    async def check_integrity(self) -> list[dict]:
        result = await self.db.execute(
            select(*_SHADOW_FIELDS)
            .where(ShadowPosition.status == "open"),
        )
        rows = result.all()
        violations: list[dict] = []
        for row in rows:
            pos_violations = []
            if row.entry_price is None or float(row.entry_price) <= 0:
                pos_violations.append("entry_price_missing_or_zero")
            if row.size_usd is None or float(row.size_usd) <= 0:
                pos_violations.append("size_usd_missing_or_zero")
            if pos_violations:
                violations.append({
                    "strategy": row.strategy,
                    "violations": pos_violations,
                })
        return violations
