import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models import Trade, Signal, ExecutionTrace

_INTEGRITY_COUNTERS: dict[str, int] = {
    "assertion_failures": 0,
    "invalid_signals_rejected": 0,
    "execution_mismatches": 0,
    "pnl_anomalies": 0,
    "trace_persist_failures": 0,
    "integrity_checks_run": 0,
}


def get_integrity_counters() -> dict[str, int]:
    return dict(_INTEGRITY_COUNTERS)


def _inc(counter: str):
    _INTEGRITY_COUNTERS[counter] = _INTEGRITY_COUNTERS.get(counter, 0) + 1


class IntegrityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_trade_integrity(self, trade: Trade, signal: Signal | None = None) -> list[str]:
        failures: list[str] = []
        total = 12

        def _check(condition: bool, msg: str):
            if not condition:
                failures.append(msg)
                _inc("assertion_failures")
                logger.warning("integrity_failure", trade_id=str(trade.id), reason=msg)

        fp = float(trade.filled_price or 0)
        fs = float(trade.filled_size or 0)
        sl = float(trade.stop_loss or 0)
        tp = float(trade.take_profit or 0)
        pnl_val = float(trade.pnl) if trade.pnl is not None else None

        # 1. entry_price > 0
        _check(fp > 0, "entry_price must be > 0")

        # 2. filled_size > 0
        _check(fs > 0, "filled_size must be > 0")

        # 3. signal.market_id == trade.market_id
        if signal and signal.market_id and trade.market_id:
            _check(signal.market_id == trade.market_id,
                   f"signal.market_id {signal.market_id} != trade.market_id {trade.market_id}")

        # 4. trade.signal_id exists
        _check(trade.signal_id is not None, "trade.signal_id must exist")

        # 5. stop_loss < entry_price for long YES
        if trade.side == "buy" and trade.outcome == "YES" and sl > 0:
            _check(sl < fp, f"stop_loss {sl} must be < entry_price {fp} for long YES")

        # 6. take_profit > entry_price for long YES
        if trade.side == "buy" and trade.outcome == "YES" and tp > 0:
            _check(tp > fp, f"take_profit {tp} must be > entry_price {fp} for long YES")

        # 7. stop_loss > entry_price for long NO (NO price = 1 - YES, inverted)
        if trade.side == "buy" and trade.outcome == "NO" and sl > 0:
            no_entry = 1.0 - fp
            no_sl = 1.0 - sl
            _check(no_sl < no_entry, f"stop_loss (NO) {no_sl} must be < entry (NO) {no_entry} for long NO")

        # 8. take_profit < entry_price for long NO (inverted)
        if trade.side == "buy" and trade.outcome == "NO" and tp > 0:
            no_entry = 1.0 - fp
            no_tp = 1.0 - tp
            _check(no_tp > no_entry, f"take_profit (NO) {no_tp} must be > entry (NO) {no_entry} for long NO")

        # 9. outcome is valid
        _check(trade.outcome in ("YES", "NO"), f"invalid outcome: {trade.outcome}")

        # 10. side is valid
        _check(trade.side in ("buy", "sell"), f"invalid side: {trade.side}")

        # 11. no NaN / negative pnl values
        if pnl_val is not None:
            _check(not math.isnan(pnl_val), "pnl is NaN")
            _check(not math.isinf(pnl_val), "pnl is inf")

        # 12. filled_price is not NaN
        _check(not math.isnan(fp), "filled_price is NaN")
        _check(not math.isinf(fp), "filled_price is inf")

        _inc("integrity_checks_run")

        for f in failures:
            logger.warning("integrity_assertion_failed", trade_id=str(trade.id), reason=f)

        return failures

    async def persist_trace(
        self,
        trade: Trade,
        signal_payload: dict | None = None,
        risk_approved: bool | None = None,
        risk_reason: str | None = None,
        market_price_at_entry: float | None = None,
        integrity_failures: list[str] | None = None,
        correlation_id: str | None = None,
    ) -> ExecutionTrace | None:
        try:
            cid = uuid.UUID(correlation_id) if correlation_id and isinstance(correlation_id, str) else correlation_id
            trace = ExecutionTrace(
                trade_id=trade.id,
                signal_id=trade.signal_id,
                market_id=trade.market_id,
                correlation_id=cid,
                signal_payload=signal_payload,
                risk_approved=risk_approved,
                risk_reason=risk_reason,
                execution_side=trade.side,
                execution_outcome=trade.outcome,
                execution_size=float(trade.size) if trade.size else None,
                fill_status=trade.status,
                fill_price=float(trade.filled_price) if trade.filled_price else None,
                fill_size=float(trade.filled_size) if trade.filled_size else None,
                slippage=float(trade.slippage) if trade.slippage else None,
                fee=float(trade.fee) if trade.fee else None,
                stop_loss=float(trade.stop_loss) if trade.stop_loss else None,
                take_profit=float(trade.take_profit) if trade.take_profit else None,
                entry_price=float(trade.filled_price or 0) if trade.filled_price else None,
                exit_price=float(trade.exit_price) if hasattr(trade, 'exit_price') else None,
                realized_pnl=float(trade.pnl) if trade.pnl else None,
                pnl_percent=float(trade.pnl_percent) if trade.pnl_percent else None,
                market_price_at_entry=market_price_at_entry,
                integrity_checks_passed=(len(integrity_failures or [])),
                integrity_checks_total=12,
                integrity_failures=integrity_failures,
                strategy_name=trade.agent_id,
                execution_timestamp=datetime.now(timezone.utc),
            )
            self.db.add(trace)
            await self.db.flush()
            logger.info("execution_trace_persisted", trace_id=str(trace.id), trade_id=str(trade.id))
            return trace
        except Exception as e:
            _inc("trace_persist_failures")
            logger.error("execution_trace_persist_failed", trade_id=str(trade.id), error=str(e))
            return None

    async def verify_and_trace(
        self,
        trade: Trade,
        signal_payload: dict | None = None,
        risk_approved: bool | None = None,
        risk_reason: str | None = None,
        market_price_at_entry: float | None = None,
        correlation_id: str | None = None,
    ) -> tuple[ExecutionTrace | None, list[str]]:
        signal: Signal | None = None
        if trade.signal_id:
            from sqlalchemy import select
            result = await self.db.execute(select(Signal).where(Signal.id == trade.signal_id))
            signal = result.scalar_one_or_none()

        failures = await self.check_trade_integrity(trade, signal=signal)
        trace = await self.persist_trace(
            trade=trade,
            signal_payload=signal_payload,
            risk_approved=risk_approved,
            risk_reason=risk_reason,
            market_price_at_entry=market_price_at_entry,
            integrity_failures=failures,
            correlation_id=correlation_id,
        )
        return trace, failures
