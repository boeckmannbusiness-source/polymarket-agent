from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_, or_, not_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models import Signal, Trade, Position, MarketEvent, AgentLog


async def run_startup_reconciliation(db: AsyncSession) -> dict:
    report = {
        "orphan_signals": 0,
        "pending_trades_no_position": 0,
        "open_positions_no_monitoring": 0,
        "stale_positions": 0,
        "stale_pending_messages": 0,
        "orphan_executions": 0,
        "recovery_actions": [],
    }

    signals_without_events = await db.execute(
        select(Signal).where(
            not_(Signal.id.in_(
                select(Trade.signal_id).where(Trade.signal_id.isnot(None))
            ))
        ).limit(100)
    )
    orphan_signals = list(signals_without_events.scalars().all())
    report["orphan_signals"] = len(orphan_signals)
    if orphan_signals:
        logger.warning("reconciliation:orphan_signals", count=len(orphan_signals))

    pending_trades = await db.execute(
        select(Trade).where(
            and_(
                Trade.status == "pending",
                Trade.filled_size <= 0,
            )
        ).limit(100)
    )
    pending_trades_list = list(pending_trades.scalars().all())
    report["pending_trades_no_position"] = len(pending_trades_list)
    if pending_trades_list:
        logger.warning("reconciliation:pending_trades", count=len(pending_trades_list))

    stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    stale_positions = await db.execute(
        select(Position).where(
            and_(
                Position.status == "OPEN",
                Position.updated_at < stale_cutoff,
            )
        ).limit(100)
    )
    stale_positions_list = list(stale_positions.scalars().all())
    report["stale_positions"] = len(stale_positions_list)
    if stale_positions_list:
        logger.warning("reconciliation:stale_positions", count=len(stale_positions_list))
        for pos in stale_positions_list[:5]:
            logger.warning(
                "reconciliation:stale_position_detail",
                position_id=str(pos.id),
                market=pos.market_condition_id,
                days_stale=(datetime.now(timezone.utc) - pos.updated_at).days if pos.updated_at else None,
            )

    open_positions_without_trades = await db.execute(
        select(Position).where(
            and_(
                Position.status == "OPEN",
                not_(Position.market_id.in_(
                    select(Trade.market_id).where(Trade.status == "open")
                )),
            )
        ).limit(100)
    )
    orphan_positions = list(open_positions_without_trades.scalars().all())
    report["open_positions_no_monitoring"] = len(orphan_positions)
    if orphan_positions:
        logger.warning("reconciliation:positions_without_monitoring", count=len(orphan_positions))

    last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    uncorrelated_executions = await db.execute(
        select(Trade).where(
            and_(
                Trade.created_at >= last_24h,
                Trade.status == "closed",
                Trade.signal_id.is_(None),
            )
        ).limit(100)
    )
    orphan_execs = list(uncorrelated_executions.scalars().all())
    report["orphan_executions"] = len(orphan_execs)
    if orphan_execs:
        logger.warning("reconciliation:orphan_executions", count=len(orphan_execs))

    if report["stale_positions"] > 0:
        for pos in stale_positions_list:
            pos.status = "CLOSED"
            pos.realized_pnl = float(pos.unrealized_pnl or 0.0)
            pos.unrealized_pnl = 0.0
            pos.closed_at = datetime.now(timezone.utc)
            report["recovery_actions"].append({
                "type": "close_stale_position",
                "position_id": str(pos.id),
                "reason": "stale_for_24h_no_updates",
            })
        await db.flush()
        logger.info("reconciliation:closed_stale_positions", count=len(stale_positions_list))

    if report["pending_trades_no_position"] > 0:
        for trade in pending_trades_list:
            trade.status = "cancelled"
            report["recovery_actions"].append({
                "type": "cancel_pending_trade",
                "trade_id": str(trade.id),
                "reason": "no_fill_after_reconciliation",
            })
        await db.flush()
        logger.info("reconciliation:cancelled_pending_trades", count=len(pending_trades_list))

    await db.commit()

    if any(report[k] > 0 for k in report if isinstance(report[k], int)):
        logger.warning("reconciliation:issues_found", report={k: v for k, v in report.items() if isinstance(v, int)})
    else:
        logger.info("reconciliation:clean_start")

    return report


async def check_redis_persistence(r) -> bool:
    from app.config import settings
    if not settings.REDIS_ENABLED:
        logger.info("redis_not_configured_skipping_persistence_check")
        return True
    try:
        config = await r.config_get("appendonly")
        aof_enabled = config.get("appendonly") == "yes"
        save_config = await r.config_get("save")
        rdb_enabled = bool(save_config.get("save"))
        if not aof_enabled and not rdb_enabled:
            logger.warning(
                "redis_persistence_disabled",
                message="Redis has no persistence enabled. Streams, consumer groups, and dedup keys will be lost on restart.",
                aof=aof_enabled,
                rdb=rdb_enabled,
            )
            return False
        logger.info(
            "redis_persistence_ok",
            aof=aof_enabled,
            rdb=rdb_enabled,
        )
        return True
    except Exception as e:
        logger.warning("redis_persistence_check_failed", error=str(e))
        return False
