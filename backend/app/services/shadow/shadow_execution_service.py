import uuid
import json
import asyncio
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from typing import Any
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Signal, Market
from app.core.logging import logger

SHADOW_EXECUTIONS_HASH = "shadow:executions"
SHADOW_PROCESSED_SIGNALS_KEY = "shadow:processed_signals"
SHADOW_LAST_SYNC_KEY = "shadow:last_sync_timestamp"


@dataclass
class ShadowExecution:
    id: str
    signal_id: str
    market_id: str
    strategy: str
    direction: str
    outcome: str
    size: float
    entry_price: float
    current_price: float | None = None
    exit_price: float | None = None
    entry_timestamp: str = ""
    exit_timestamp: str | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    status: str = "open"
    outcome_resolved: bool = False
    resolution_price: float | None = None
    signal_confidence: float = 0.0


class ShadowExecutionService:
    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self._executions: dict[str, ShadowExecution] = {}
        self._initialized = False

    async def _ensure_redis(self):
        if not self._initialized:
            self._initialized = True
            await self._load_from_redis()

    async def _safe_redis(self):
        try:
            from app.redis import get_redis
            return await get_redis()
        except Exception:
            return None

    async def _load_from_redis(self):
        r = await self._safe_redis()
        if not r:
            return
        try:
            execution_ids = await r.hkeys(SHADOW_EXECUTIONS_HASH)
            for eid in execution_ids:
                eid_str = eid.decode() if isinstance(eid, bytes) else str(eid)
                data = await r.hget(SHADOW_EXECUTIONS_HASH, eid_str)
                if data:
                    parsed = json.loads(data)
                    self._executions[eid_str] = ShadowExecution(**parsed)
        except Exception as e:
            logger.warning("shadow_load_redis_failed", error=str(e))

    async def _save_to_redis(self, execution: ShadowExecution):
        r = await self._safe_redis()
        if not r:
            return
        try:
            await r.hset(
                SHADOW_EXECUTIONS_HASH,
                execution.id,
                json.dumps(asdict(execution), default=str),
            )
        except Exception as e:
            logger.warning("shadow_save_redis_failed", error=str(e))

    async def create_execution(
        self,
        signal_id: str,
        market_id: str,
        strategy: str,
        direction: str,
        outcome: str,
        size: float,
        entry_price: float,
        signal_confidence: float = 0.0,
    ) -> ShadowExecution:
        await self._ensure_redis()
        exec_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        execution = ShadowExecution(
            id=exec_id,
            signal_id=signal_id,
            market_id=market_id,
            strategy=strategy,
            direction=direction,
            outcome=outcome,
            size=size,
            entry_price=entry_price,
            entry_timestamp=now,
            signal_confidence=signal_confidence,
        )
        self._executions[exec_id] = execution
        await self._save_to_redis(execution)
        logger.info("shadow_execution_created", id=exec_id, signal_id=signal_id, strategy=strategy)
        return execution

    async def update_current_price(
        self, execution_id: str, current_price: float
    ) -> ShadowExecution | None:
        """
        Updates the current price and recalculates unrealized PnL.
        NOTE: This method is being refactored to use PriceResolver in Sprint 2.0.
        Current implementation maintains float compatibility for the existing shadow layer.
        """
        from app.services.shadow.pnl_utils import compute_shadow_pnl
        r = await self._safe_redis()
        if not r:
            return None

        retries = 0
        async with r.pipeline(transaction=True) as pipe:
            while retries < 5:
                try:
                    await pipe.watch(SHADOW_EXECUTIONS_HASH)
                    raw = await r.hget(SHADOW_EXECUTIONS_HASH, execution_id)
                    if not raw:
                        return None

                    data = json.loads(raw)
                    execution = ShadowExecution(**data)

                    if execution.status == "closed":
                        return None

                    execution.current_price = current_price
                    # size is USD not quantity
                    pnl = compute_shadow_pnl(
                        entry_price=Decimal(str(execution.entry_price)),
                        exit_price=Decimal(str(current_price)),
                        size_usd=Decimal(str(execution.size))
                    )
                    if execution.direction == "buy":
                        execution.unrealized_pnl = float(pnl)
                    else:
                        execution.unrealized_pnl = -float(pnl)

                    pipe.multi()
                    pipe.hset(
                        SHADOW_EXECUTIONS_HASH,
                        execution_id,
                        json.dumps(asdict(execution), default=str),
                    )
                    await pipe.execute()
                    self._executions[execution_id] = execution
                    return execution
                except Exception as e:
                    retries += 1
                    if retries >= 5:
                        logger.error("shadow_execution_redis_update_failed", id=execution_id, error=str(e), exc_info=True)
                        return None
                    await asyncio.sleep(0.01)
                    continue
        return None

    async def close_execution(
        self,
        execution_id: str,
        exit_price: float,
        exit_timestamp: str | None = None,
    ) -> ShadowExecution | None:
        from app.services.shadow.pnl_utils import compute_shadow_pnl
        r = await self._safe_redis()
        if not r:
            return None

        retries = 0
        async with r.pipeline(transaction=True) as pipe:
            while retries < 5:
                try:
                    await pipe.watch(SHADOW_EXECUTIONS_HASH)
                    raw = await r.hget(SHADOW_EXECUTIONS_HASH, execution_id)
                    if not raw:
                        return None

                    data = json.loads(raw)
                    execution = ShadowExecution(**data)

                    if execution.status == "closed":
                        return None

                    execution.exit_price = exit_price
                    execution.exit_timestamp = exit_timestamp or datetime.now(timezone.utc).isoformat()
                    execution.outcome_resolved = True
                    execution.resolution_price = exit_price
                    execution.status = "closed"

                    # size is USD not quantity
                    pnl = compute_shadow_pnl(
                        entry_price=Decimal(str(execution.entry_price)),
                        exit_price=Decimal(str(exit_price)),
                        size_usd=Decimal(str(execution.size))
                    )
                    if execution.direction == "buy":
                        execution.realized_pnl = float(pnl)
                    else:
                        execution.realized_pnl = -float(pnl)
                    execution.unrealized_pnl = 0.0

                    pipe.multi()
                    pipe.hset(
                        SHADOW_EXECUTIONS_HASH,
                        execution_id,
                        json.dumps(asdict(execution), default=str),
                    )
                    await pipe.execute()
                    self._executions[execution_id] = execution
                    logger.info("shadow_execution_closed", id=execution_id, pnl=execution.realized_pnl)
                    return execution
                except Exception as e:
                    retries += 1
                    if retries >= 5:
                        logger.error("shadow_execution_redis_close_failed", id=execution_id, error=str(e), exc_info=True)
                        return None
                    await asyncio.sleep(0.01)
                    continue
        return None

    async def process_signal(self, signal: dict[str, Any]) -> ShadowExecution | None:
        """
        Processes a signal into a shadow execution without binary assumptions.
        """
        # Venue-neutral price resolution from signal
        entry_price = signal.get("price") or signal.get("estimated_probability") or signal.get("implied_probability") or 0.0
        entry_price = float(entry_price)

        confidence = float(signal.get("confidence", 0.5))
        base_size = 100.0
        size = base_size * confidence
        direction = signal.get("direction", "buy")

        # Outcome is now optional and venue-neutral
        outcome = signal.get("outcome")
        strategy = signal.get("source_agent") or signal.get("signal_type") or "unknown"

        return await self.create_execution(
            signal_id=str(signal["id"]),
            market_id=str(signal["market_id"]),
            strategy=strategy,
            direction=direction,
            outcome=outcome or "NONE",
            size=size,
            entry_price=entry_price,
            signal_confidence=confidence,
        )

    async def sync_from_signals(self, db: AsyncSession) -> dict[str, Any]:
        processed_ids: set[str] = set()
        r = await self._safe_redis()
        if r:
            try:
                raw = await r.smembers(SHADOW_PROCESSED_SIGNALS_KEY)
                processed_ids = {x.decode() if isinstance(x, bytes) else str(x) for x in raw}
            except Exception:
                pass

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        result = await db.execute(
            select(Signal)
            .where(Signal.generated_at >= cutoff, Signal.is_active == True)
            .order_by(Signal.generated_at.asc())
        )
        signals = list(result.scalars().all())

        created = 0
        skipped = 0
        for signal in signals:
            sid = str(signal.id)
            if sid in processed_ids:
                skipped += 1
                continue
            signal_dict = {
                "id": sid,
                "market_id": str(signal.market_id) if signal.market_id else "",
                "signal_type": signal.signal_type,
                "direction": signal.direction,
                "confidence": float(signal.confidence),
                "implied_probability": (
                    float(signal.implied_probability) if signal.implied_probability else None
                ),
                "estimated_probability": (
                    float(signal.estimated_probability) if signal.estimated_probability else None
                ),
                "source_agent": signal.source_agent,
                "generated_at": signal.generated_at.isoformat() if signal.generated_at else "",
            }
            try:
                await self.process_signal(signal_dict)
                processed_ids.add(sid)
                created += 1
            except Exception as e:
                logger.warning("shadow_sync_signal_failed", signal_id=sid, error=str(e))

        if r and created > 0:
            try:
                pipe = r.pipeline()
                for sid in list(processed_ids)[-5000:]:
                    pipe.sadd(SHADOW_PROCESSED_SIGNALS_KEY, sid)
                await pipe.execute()
            except Exception as e:
                logger.warning("shadow_sync_persist_failed", error=str(e))

        if r:
            try:
                await r.set(SHADOW_LAST_SYNC_KEY, datetime.now(timezone.utc).isoformat())
            except Exception:
                pass

        return {"created": created, "skipped": skipped, "total_signals": len(signals)}

    async def refresh_prices(self, db: AsyncSession) -> dict[str, Any]:
        """
        Refreshes prices using the venue-neutral PriceResolver interface.
        """
        from app.services.shadow.pricing.venue_price_resolver import VenuePriceResolver
        from app.domain.assets import AssetId, AssetResolution, Asset, AssetMetadata

        open_execs = [e for e in self._executions.values() if e.status == "open"]
        if not open_execs:
            return {"updated": 0}

        resolver = VenuePriceResolver()
        updated = 0
        closed = 0

        for exec_ in open_execs:
            # Create a mock resolution for now as we are decoupling
            # In Sprint 2.0, this will use AssetRegistry.resolve()
            asset_res = AssetResolution(
                asset=Asset(
                    asset_id=AssetId(venue="unknown", symbol=exec_.outcome, canonical_id=exec_.market_id),
                    decimals=18,
                    metadata=AssetMetadata()
                ),
                source="shadow",
                confidence=1.0
            )

            price = await resolver.resolve_price(asset_res)
            if price is not None:
                await self.update_current_price(exec_.id, float(price))
                updated += 1

        return {"updated": updated, "closed": closed}

    def get_all_executions(self) -> list[ShadowExecution]:
        return list(self._executions.values())

    def get_execution(self, execution_id: str) -> ShadowExecution | None:
        return self._executions.get(execution_id)

    def get_open_executions(self) -> list[ShadowExecution]:
        return [e for e in self._executions.values() if e.status == "open"]

    def get_closed_executions(self) -> list[ShadowExecution]:
        return [e for e in self._executions.values() if e.status == "closed"]

    def get_executions_by_strategy(self, strategy: str) -> list[ShadowExecution]:
        return [e for e in self._executions.values() if e.strategy == strategy]

    def get_executions_by_market(self, market_id: str) -> list[ShadowExecution]:
        return [e for e in self._executions.values() if e.market_id == market_id]

    def get_strategy_performance(self, strategy: str) -> dict[str, Any]:
        execs = self.get_executions_by_strategy(strategy)
        closed = [e for e in execs if e.status == "closed"]
        total = len(execs)
        closed_count = len(closed)
        open_count = total - closed_count
        realized_pnls = [e.realized_pnl for e in closed if e.realized_pnl is not None]
        total_pnl = sum(realized_pnls) if realized_pnls else 0.0
        win_count = sum(1 for p in realized_pnls if p > 0)
        loss_count = sum(1 for p in realized_pnls if p < 0)
        win_rate = win_count / len(realized_pnls) if realized_pnls else 0.0
        unrealized_pnls = [
            e.unrealized_pnl
            for e in execs
            if e.unrealized_pnl is not None and e.status == "open"
        ]
        total_unrealized = sum(unrealized_pnls) if unrealized_pnls else 0.0
        avg_pnl = total_pnl / len(realized_pnls) if realized_pnls else 0.0
        variance = (
            sum((p - avg_pnl) ** 2 for p in realized_pnls) / len(realized_pnls)
            if len(realized_pnls) > 1
            else 1
        )
        sharpe = (
            avg_pnl / (variance ** 0.5 + 0.0001) * (252 ** 0.5)
            if realized_pnls
            else 0.0
        )

        return {
            "strategy": strategy,
            "total_executions": total,
            "closed_executions": closed_count,
            "open_executions": open_count,
            "total_realized_pnl": round(total_pnl, 4),
            "total_unrealized_pnl": round(total_unrealized, 4),
            "total_pnl": round(total_pnl + total_unrealized, 4),
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": round(win_rate, 4),
            "avg_pnl": round(avg_pnl, 6),
            "sharpe": round(sharpe, 4),
        }

    def get_all_strategy_performance(self) -> list[dict[str, Any]]:
        strategies = set(e.strategy for e in self._executions.values())
        return [self.get_strategy_performance(s) for s in sorted(strategies)]

    def get_overall_performance(self) -> dict[str, Any]:
        strategies = self.get_all_strategy_performance()
        total_executions = sum(s["total_executions"] for s in strategies)
        total_realized = sum(s["total_realized_pnl"] for s in strategies)
        total_unrealized = sum(s["total_unrealized_pnl"] for s in strategies)
        total_wins = sum(s["win_count"] for s in strategies)
        total_losses = sum(s["loss_count"] for s in strategies)
        total_closed = sum(s["closed_executions"] for s in strategies)
        total_open = sum(s["open_executions"] for s in strategies)

        all_closed_pnls = [
            e.realized_pnl
            for e in self._executions.values()
            if e.status == "closed" and e.realized_pnl is not None
        ]
        win_rate = (
            total_wins / (total_wins + total_losses)
            if (total_wins + total_losses) > 0
            else 0.0
        )
        avg_pnl = sum(all_closed_pnls) / len(all_closed_pnls) if all_closed_pnls else 0.0
        variance = (
            sum((p - avg_pnl) ** 2 for p in all_closed_pnls) / len(all_closed_pnls)
            if len(all_closed_pnls) > 1
            else 1
        )
        sharpe = (
            avg_pnl / (variance ** 0.5 + 0.0001) * (252 ** 0.5)
            if all_closed_pnls
            else 0.0
        )

        return {
            "total_executions": total_executions,
            "closed_executions": total_closed,
            "open_executions": total_open,
            "total_realized_pnl": round(total_realized, 4),
            "total_unrealized_pnl": round(total_unrealized, 4),
            "total_pnl": round(total_realized + total_unrealized, 4),
            "win_count": total_wins,
            "loss_count": total_losses,
            "win_rate": round(win_rate, 4),
            "avg_pnl": round(avg_pnl, 6),
            "sharpe": round(sharpe, 4),
            "strategy_count": len(strategies),
        }

    def reset(self):
        self._executions = {}
        self._initialized = False


shadow_execution_service = ShadowExecutionService()
