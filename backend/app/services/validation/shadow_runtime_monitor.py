from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.events import EventBus
from app.database import async_session_factory
from app.models.shadow_decision_log import ShadowDecisionLog
from app.models.shadow_validation_snapshot import ShadowValidationSnapshot
from app.models.market import MarketEvent, Market
from app.models.wallet import WalletTrade, Wallet
from app.models.signal import Signal
from app.models.trade import Trade
from app.redis import get_redis


REDIS_AGENT_EVENT_STREAM = "agent:event"
AGENT_STARTED_EVENT = "agent.started"


class ShadowRuntimeMonitor:
    def __init__(self):
        self._last_decision_count: int = 0
        self._last_decision_check: datetime | None = None
        self._last_signal_count: int = 0
        self._last_signal_check: datetime | None = None
        self._last_wallet_trade_count: int = 0
        self._active_alerts: dict[str, dict[str, Any]] = {}
        self._start_time: datetime = datetime.now(timezone.utc)
        self._snapshot_count: int = 0

    async def collect_and_persist(self) -> dict[str, Any]:
        try:
            async with async_session_factory() as db:
                snapshot_data = await self._collect_metrics(db)
                await self._persist_snapshot(db, snapshot_data)
                failures = await self._detect_failures(db)
                for alert in failures:
                    if alert is not None:
                        await self._emit_alert(alert)
                snapshot_data["active_alerts"] = list(self._active_alerts.values())
                snapshot_data["failures_detected"] = len([f for f in failures if f is not None])
                elapsed = (datetime.now(timezone.utc) - self._start_time).total_seconds()
                snapshot_data["validation_progress_hours"] = round(elapsed / 3600, 1)
                return snapshot_data
        except Exception as e:
            logger.error("shadow_runtime_monitor_failed", error=str(e))
            return {"error": str(e)}

    async def _collect_metrics(self, db: AsyncSession) -> dict[str, Any]:
        market_data_count = await db.execute(
            select(func.count(MarketEvent.id))
        )
        wallet_trade_count = await db.execute(
            select(func.count(WalletTrade.id))
        )
        signal_count = await db.execute(
            select(func.count(Signal.id))
        )
        trade_request_count = await db.execute(
            select(func.count(Trade.id)).where(
                Trade.status.in_(["pending", "open", "filled"])
            )
        )
        shadow_decision_count = await db.execute(
            select(func.count(ShadowDecisionLog.id))
        )
        risk_approved_count = await db.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.safety_gate_decision == "SHADOW_APPROVED"
            )
        )
        risk_rejected_count = await db.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.safety_gate_decision == "SHADOW_BLOCKED"
            )
        )
        unique_wallets = await db.execute(
            select(func.count(Wallet.address))
        )
        unique_markets = await db.execute(
            select(func.count(Market.id))
        )

        from app.services.safety.execution_safety_gate import execution_safety_gate
        gate_metrics = execution_safety_gate.get_metrics_snapshot()

        return {
            "market_data_count": market_data_count.scalar() or 0,
            "wallet_trade_count": wallet_trade_count.scalar() or 0,
            "signal_count": signal_count.scalar() or 0,
            "trade_request_count": trade_request_count.scalar() or 0,
            "shadow_decision_count": shadow_decision_count.scalar() or 0,
            "risk_approved_count": risk_approved_count.scalar() or 0,
            "risk_rejected_count": risk_rejected_count.scalar() or 0,
            "shadow_approved_count": gate_metrics.get("execution_allowed_total", 0),
            "shadow_blocked_count": gate_metrics.get("execution_blocks_total", 0),
            "unique_wallets": unique_wallets.scalar() or 0,
            "unique_markets": unique_markets.scalar() or 0,
            "exception_count": 0,
        }

    async def _persist_snapshot(self, db: AsyncSession, data: dict[str, Any]):
        snapshot = ShadowValidationSnapshot(
            market_data_count=data["market_data_count"],
            wallet_trade_count=data["wallet_trade_count"],
            signal_count=data["signal_count"],
            trade_request_count=data["trade_request_count"],
            shadow_decision_count=data["shadow_decision_count"],
            risk_approved_count=data["risk_approved_count"],
            risk_rejected_count=data["risk_rejected_count"],
            shadow_approved_count=data["shadow_approved_count"],
            shadow_blocked_count=data["shadow_blocked_count"],
            unique_wallets=data["unique_wallets"],
            unique_markets=data["unique_markets"],
            exception_count=data["exception_count"],
        )
        db.add(snapshot)
        await db.commit()

        self._snapshot_count += 1
        logger.info("shadow_validation_snapshot_persisted", id=str(snapshot.id), timestamp=str(snapshot.timestamp))

    async def _detect_failures(self, db: AsyncSession) -> list[dict[str, Any] | None]:
        return [
            await self._check_pipeline_stall(db),
            await self._check_signal_generation_failure(db),
            await self._check_execution_pipeline_failure(db),
            await self._check_agent_restart_loop(),
            await self._check_db_persistence_failure(db),
        ]

    async def _check_pipeline_stall(self, db: AsyncSession) -> dict[str, Any] | None:
        result = await db.execute(
            select(func.count(ShadowDecisionLog.id))
        )
        current_count = result.scalar() or 0
        now = datetime.now(timezone.utc)

        if self._last_decision_check is not None:
            elapsed = (now - self._last_decision_check).total_seconds()
            if current_count == self._last_decision_count and elapsed > 1800:
                return self._build_alert(
                    "PIPELINE_STALL",
                    "CRITICAL",
                    f"ShadowDecisionLog unchanged for {elapsed:.0f}s (>30min). Count remains {current_count}.",
                )

        self._last_decision_count = current_count
        self._last_decision_check = now
        return None

    async def _check_signal_generation_failure(self, db: AsyncSession) -> dict[str, Any] | None:
        wallet_result = await db.execute(select(func.count(WalletTrade.id)))
        current_wallet_trades = wallet_result.scalar() or 0
        signal_result = await db.execute(select(func.count(Signal.id)))
        current_signals = signal_result.scalar() or 0
        now = datetime.now(timezone.utc)

        if self._last_wallet_trade_count > 0 and self._last_signal_check is not None:
            wallet_increasing = current_wallet_trades > self._last_wallet_trade_count
            signal_flat = current_signals == self._last_signal_count
            elapsed = (now - self._last_signal_check).total_seconds()
            if wallet_increasing and signal_flat and elapsed > 900:
                return self._build_alert(
                    "SIGNAL_GENERATION_FAILURE",
                    "HIGH",
                    f"wallet:trade increasing ({self._last_wallet_trade_count}->{current_wallet_trades}) "
                    f"but signal:generated flat ({current_signals}) for >15min.",
                )

        self._last_wallet_trade_count = current_wallet_trades
        self._last_signal_count = current_signals
        self._last_signal_check = now
        return None

    async def _check_execution_pipeline_failure(self, db: AsyncSession) -> dict[str, Any] | None:
        signal_result = await db.execute(select(func.count(Signal.id)))
        current_signals = signal_result.scalar() or 0
        decision_result = await db.execute(select(func.count(ShadowDecisionLog.id)))
        current_decisions = decision_result.scalar() or 0

        if not hasattr(self, "_last_exec_signal_count"):
            self._last_exec_signal_count = current_signals
            self._last_exec_decision_count = current_decisions
            self._last_exec_check = datetime.now(timezone.utc)
            return None

        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_exec_check).total_seconds()
        if current_signals > self._last_exec_signal_count and current_decisions == self._last_exec_decision_count and elapsed > 900:
            return self._build_alert(
                "EXECUTION_PIPELINE_FAILURE",
                "HIGH",
                f"signal:generated increasing ({self._last_exec_signal_count}->{current_signals}) "
                f"but shadow_decision_log flat ({current_decisions}) for >15min.",
            )

        self._last_exec_signal_count = current_signals
        self._last_exec_decision_count = current_decisions
        self._last_exec_check = now
        return None

    async def _check_agent_restart_loop(self) -> dict[str, Any] | None:
        try:
            r = await get_redis()
            thirty_min_ago_ms = int((datetime.now(timezone.utc) - timedelta(minutes=30)).timestamp() * 1000)
            raw = await r.xrevrange(REDIS_AGENT_EVENT_STREAM, max="+", min=thirty_min_ago_ms, count=100)
            start_events = []
            for msg_id, fields in raw:
                event_type = fields.get(b"event_type", b"").decode() if isinstance(fields.get(b"event_type"), bytes) else fields.get("event_type", "")
                if AGENT_STARTED_EVENT in event_type:
                    start_events.append({"msg_id": msg_id, "fields": fields})

            if len(start_events) >= 3:
                return self._build_alert(
                    "AGENT_RESTART_LOOP",
                    "CRITICAL",
                    f"agent.started event appears {len(start_events)} times in last 30min (from Redis stream). Restart loop likely.",
                    details={"start_event_count": len(start_events)},
                )
        except Exception as e:
            logger.warning("shadow_validation_redis_stream_check_failed", error=str(e))

        return None

    async def _check_db_persistence_failure(self, db: AsyncSession) -> dict[str, Any] | None:
        thirty_min_ago = datetime.now(timezone.utc) - timedelta(minutes=30)

        shadow_result = await db.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.timestamp >= thirty_min_ago
            )
        )
        recent_decision_count = shadow_result.scalar() or 0

        if self._snapshot_count > 6 and recent_decision_count == 0:
            return self._build_alert(
                "DATABASE_PERSISTENCE_FAILURE",
                "CRITICAL",
                f"No ShadowDecisionLog writes in last 30min (monitor running {self._snapshot_count} cycles). DB persistence may be down.",
            )
        return None

    def _build_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)

        if alert_type in self._active_alerts:
            existing = self._active_alerts[alert_type]
            if existing["severity"] == severity and existing["status"] == "active":
                return None

        alert = {
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "details": details or {},
            "timestamp": now.isoformat(),
            "status": "active",
        }
        self._active_alerts[alert_type] = alert
        return alert

    async def _emit_alert(self, alert: dict[str, Any]):
        logger.warning(
            "shadow_validation_alert",
            alert_type=alert["alert_type"],
            severity=alert["severity"],
            message=alert["message"],
        )

        try:
            await EventBus.publish(
                "system:alert",
                "shadow.validation.alert",
                "shadow_runtime_monitor",
                {
                    "alert_type": alert["alert_type"],
                    "severity": alert["severity"],
                    "message": alert["message"],
                    "details": alert.get("details", {}),
                },
            )
        except Exception as e:
            logger.warning("shadow_validation_alert_publish_failed", error=str(e))

        try:
            from app.services.stream.event_store import event_store
            await event_store.store({
                "event_id": str(__import__("uuid").uuid4()),
                "event_type": "shadow.validation.alert",
                "entity_type": "shadow_validation",
                "entity_id": alert["alert_type"],
                "sequence": 0,
                "timestamp": alert["timestamp"],
                "payload": alert,
            })
        except Exception as e:
            logger.warning("shadow_validation_alert_store_failed", error=str(e))

        try:
            from app.ws.manager import manager
            await manager.broadcast_event(
                {
                    "event_id": str(__import__("uuid").uuid4()),
                    "event_type": "shadow.validation.alert",
                    "source": "shadow_runtime_monitor",
                    "timestamp": alert["timestamp"],
                    "data": alert,
                },
                channels=["monitoring"],
            )
        except Exception as e:
            logger.warning("shadow_validation_alert_ws_failed", error=str(e))

    async def get_latest_snapshot(self, db: AsyncSession) -> dict[str, Any] | None:
        result = await db.execute(
            select(ShadowValidationSnapshot)
            .order_by(ShadowValidationSnapshot.timestamp.desc())
            .limit(1)
        )
        snap = result.scalar_one_or_none()
        if snap is None:
            return None
        return {
            "id": str(snap.id),
            "timestamp": snap.timestamp.isoformat() if snap.timestamp else "",
            "market_data_count": snap.market_data_count,
            "wallet_trade_count": snap.wallet_trade_count,
            "signal_count": snap.signal_count,
            "trade_request_count": snap.trade_request_count,
            "shadow_decision_count": snap.shadow_decision_count,
            "risk_approved_count": snap.risk_approved_count,
            "risk_rejected_count": snap.risk_rejected_count,
            "shadow_approved_count": snap.shadow_approved_count,
            "shadow_blocked_count": snap.shadow_blocked_count,
            "unique_wallets": snap.unique_wallets,
            "unique_markets": snap.unique_markets,
            "exception_count": snap.exception_count,
        }

    async def get_snapshot_history(
        self, db: AsyncSession, limit: int = 100, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        query = select(ShadowValidationSnapshot).order_by(ShadowValidationSnapshot.timestamp.desc()).limit(limit)
        if since:
            query = query.where(ShadowValidationSnapshot.timestamp >= since)
        result = await db.execute(query)
        snapshots = list(result.scalars().all())
        return [
            {
                "id": str(s.id),
                "timestamp": s.timestamp.isoformat() if s.timestamp else "",
                "market_data_count": s.market_data_count,
                "wallet_trade_count": s.wallet_trade_count,
                "signal_count": s.signal_count,
                "trade_request_count": s.trade_request_count,
                "shadow_decision_count": s.shadow_decision_count,
                "risk_approved_count": s.risk_approved_count,
                "risk_rejected_count": s.risk_rejected_count,
                "shadow_approved_count": s.shadow_approved_count,
                "shadow_blocked_count": s.shadow_blocked_count,
                "unique_wallets": s.unique_wallets,
                "unique_markets": s.unique_markets,
                "exception_count": s.exception_count,
            }
            for s in snapshots
        ]

    async def get_validation_status(self) -> dict[str, Any]:
        elapsed = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        elapsed_hours = round(elapsed / 3600, 1)

        max_severity = "HEALTHY"
        for alert in self._active_alerts.values():
            if alert["severity"] == "CRITICAL":
                max_severity = "CRITICAL"
                break
            elif alert["severity"] == "HIGH" and max_severity != "CRITICAL":
                max_severity = "WARNING"

        return {
            "status": max_severity,
            "elapsed_hours": elapsed_hours,
            "total_hours": 72,
            "progress_pct": round(min(elapsed_hours / 72 * 100, 100), 1),
            "snapshot_count": self._snapshot_count,
            "active_alert_count": len(self._active_alerts),
            "start_time": self._start_time.isoformat(),
        }

    def get_active_alerts(self) -> list[dict[str, Any]]:
        return list(self._active_alerts.values())

    def resolve_alert(self, alert_type: str):
        if alert_type in self._active_alerts:
            self._active_alerts[alert_type]["status"] = "resolved"
            del self._active_alerts[alert_type]


shadow_runtime_monitor = ShadowRuntimeMonitor()
