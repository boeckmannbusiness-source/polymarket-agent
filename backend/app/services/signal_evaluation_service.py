from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models import Signal, MarketEvent, SignalOutcome

if TYPE_CHECKING:
    from app.replay.engine import ReplayedSignal


class SignalEvaluationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_replayed_signal(self, replayed: ReplayedSignal) -> SignalOutcome:
        holding = 0
        if replayed.holding_time_seconds:
            holding = replayed.holding_time_seconds
        elif replayed.outcome_4h:
            holding = 14400
        elif replayed.outcome_1h:
            holding = 3600
        elif replayed.outcome_15m:
            holding = 900
        elif replayed.outcome_5m:
            holding = 300

        outcome = SignalOutcome(
            strategy_name=replayed.strategy_name,
            entry_timestamp=replayed.entry_timestamp,
            entry_probability=replayed.signal.confidence,
            entry_confidence=replayed.signal.confidence,
            signal_direction=replayed.signal.signal,
            outcome_5m=replayed.outcome_5m,
            probability_5m=replayed.probability_5m,
            pnl_5m=replayed.pnl_5m,
            outcome_15m=replayed.outcome_15m,
            probability_15m=replayed.probability_15m,
            pnl_15m=replayed.pnl_15m,
            outcome_1h=replayed.outcome_1h,
            probability_1h=replayed.probability_1h,
            pnl_1h=replayed.pnl_1h,
            outcome_4h=replayed.outcome_4h,
            probability_4h=replayed.probability_4h,
            pnl_4h=replayed.pnl_4h,
            outcome_close=replayed.outcome_close,
            probability_close=replayed.probability_close,
            pnl_close=replayed.pnl_close,
            max_favorable_excursion=replayed.max_favorable_excursion,
            max_adverse_excursion=replayed.max_adverse_excursion,
            reversal_count=replayed.reversal_count,
            holding_time_seconds=holding or None,
            evaluation_epoch="post_semantic_fix",
        )
        self.db.add(outcome)
        await self.db.flush()
        return outcome

    async def _get_entry_price(self, signal: Signal, entry_ts: datetime) -> Decimal | None:
        from app.services.price_utils import get_outcome_specific_price

        result = await get_outcome_specific_price(
            self.db, signal.market_id, entry_ts, signal.direction or "BUY_YES"
        )
        if result is not None:
            return result

        entry_price_result = await self.db.execute(
            select(MarketEvent.price)
            .where(
                MarketEvent.market_id == signal.market_id,
                MarketEvent.timestamp <= entry_ts,
            )
            .order_by(desc(MarketEvent.timestamp))
            .limit(1)
        )
        entry_price_row = entry_price_result.one_or_none()
        if entry_price_row and entry_price_row[0] is not None:
            return Decimal(str(entry_price_row[0]))
        return None

    async def evaluate_signal(self, signal: Signal) -> SignalOutcome | None:
        if signal.generated_at is None or signal.market_id is None:
            return None

        events_result = await self.db.execute(
            select(MarketEvent)
            .where(
                MarketEvent.market_id == signal.market_id,
                MarketEvent.timestamp >= signal.generated_at,
            )
            .order_by(MarketEvent.timestamp)
        )
        events = list(events_result.scalars().all())

        if not events:
            return None

        entry_ts = signal.generated_at.replace(tzinfo=timezone.utc) if signal.generated_at.tzinfo is None else signal.generated_at

        entry_price_dec = await self._get_entry_price(signal, entry_ts)
        if entry_price_dec is None:
            from app.services.pipeline_metrics import inc_signal_eval_missing_entry_price
            await inc_signal_eval_missing_entry_price()
            logger.warning(
                "signal_eval_missing_entry_price",
                signal_id=str(signal.id),
                strategy=signal.signal_type,
                market_id=str(signal.market_id),
            )
            return None

        entry_price = float(entry_price_dec)

        checkpoints = {
            "5m": entry_ts + timedelta(minutes=5),
            "15m": entry_ts + timedelta(minutes=15),
            "1h": entry_ts + timedelta(hours=1),
            "4h": entry_ts + timedelta(hours=4),
        }
        results: dict[str, dict] = {}
        mfe = 0.0
        mae = 0.0
        reversal_count = 0
        prev_direction: str | None = None

        for event in events:
            price = float(event.price) if event.price else None
            if price is None:
                continue
            event_outcome = event.outcome.upper() if event.outcome else None
            event_price = float(event.price)
            if signal.direction in ("bullish", "BUY_YES"):
                resolved_price = event_price if event_outcome == "YES" else (
                    1.0 - event_price if event_outcome == "NO" else event_price
                )
            elif signal.direction in ("bearish", "BUY_NO"):
                resolved_price = event_price if event_outcome == "NO" else (
                    1.0 - event_price if event_outcome == "YES" else event_price
                )
            else:
                resolved_price = event_price

            movement = resolved_price - entry_price
            if signal.direction in ("bullish", "BUY_YES"):
                price_direction = movement
            elif signal.direction in ("bearish", "BUY_NO"):
                price_direction = -movement
            else:
                price_direction = 0.0

            if price_direction > mfe:
                mfe = price_direction
            if price_direction < mae:
                mae = price_direction

            direction = "up" if price_direction > 0 else "down" if price_direction < 0 else "flat"
            if prev_direction and direction != prev_direction and direction != "flat":
                reversal_count += 1
            if direction != "flat":
                prev_direction = direction

            ts = event.timestamp.replace(tzinfo=timezone.utc) if event.timestamp.tzinfo is None else event.timestamp
            for label, deadline in checkpoints.items():
                if label not in results and ts >= deadline:
                    win = price_direction > 0.001 * entry_price
                    loss = price_direction < -0.001 * entry_price
                    results[label] = {
                        "outcome": "WIN" if win else "LOSS" if loss else "FLAT",
                        "probability": resolved_price,
                        "pnl": price_direction,
                    }

        pnl_close = mfe + mae if results else None
        outcome_close = None
        if results:
            last_key = sorted(results.keys(), key=lambda k: {"5m": 0, "15m": 1, "1h": 2, "4h": 3}[k])[-1]
            outcome_close = results[last_key]["outcome"]

        outcome = SignalOutcome(
            signal_id=signal.id,
            strategy_name=signal.signal_type,
            market_id=signal.market_id,
            entry_timestamp=entry_ts,
            entry_probability=signal.confidence,
            entry_confidence=signal.confidence,
            outcome_5m=results.get("5m", {}).get("outcome"),
            probability_5m=results.get("5m", {}).get("probability"),
            pnl_5m=results.get("5m", {}).get("pnl"),
            outcome_15m=results.get("15m", {}).get("outcome"),
            probability_15m=results.get("15m", {}).get("probability"),
            pnl_15m=results.get("15m", {}).get("pnl"),
            outcome_1h=results.get("1h", {}).get("outcome"),
            probability_1h=results.get("1h", {}).get("probability"),
            pnl_1h=results.get("1h", {}).get("pnl"),
            outcome_4h=results.get("4h", {}).get("outcome"),
            probability_4h=results.get("4h", {}).get("probability"),
            pnl_4h=results.get("4h", {}).get("pnl"),
            outcome_close=outcome_close,
            probability_close=results.get("4h", {}).get("probability") or results.get("1h", {}).get("probability"),
            pnl_close=pnl_close,
            max_favorable_excursion=mfe if mfe != 0 else None,
            max_adverse_excursion=mae if mae != 0 else None,
            reversal_count=reversal_count,
            holding_time_seconds=int((min(checkpoints["4h"], entry_ts + timedelta(hours=4)) - entry_ts).total_seconds()) if results else None,
        )
        self.db.add(outcome)
        await self.db.flush()
        return outcome

    async def evaluate_pending_signals(self, max_signals: int = 50) -> list[SignalOutcome]:
        existing = select(SignalOutcome.signal_id)
        existing_result = await self.db.execute(existing)
        existing_ids = {r[0] for r in existing_result.all() if r[0]}

        query = (
            select(Signal)
            .where(Signal.id.notin_(existing_ids) if existing_ids else True)
            .order_by(desc(Signal.generated_at))
            .limit(max_signals)
        )
        result = await self.db.execute(query)
        signals = list(result.scalars().all())

        outcomes = []
        for signal in signals:
            try:
                outcome = await self.evaluate_signal(signal)
                if outcome:
                    outcomes.append(outcome)
            except Exception:
                continue

        return outcomes

    async def get_outcomes(self, strategy_name: str | None = None, limit: int = 100):
        query = select(SignalOutcome)
        if strategy_name:
            query = query.where(SignalOutcome.strategy_name == strategy_name)
        query = query.order_by(desc(SignalOutcome.entry_timestamp)).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_strategy_summary(self, strategy_name: str) -> dict:
        outcomes = await self.get_outcomes(strategy_name, limit=1000)
        if not outcomes:
            return {"strategy": strategy_name, "total_signals": 0}

        total = len(outcomes)
        wins = sum(1 for o in outcomes if o.outcome_close == "WIN")
        losses = sum(1 for o in outcomes if o.outcome_close == "LOSS")
        flats = sum(1 for o in outcomes if o.outcome_close == "FLAT")
        timed_out = sum(1 for o in outcomes if o.outcome_close is None)

        win_rate = wins / total if total > 0 else 0
        pnls = [float(o.pnl_close) for o in outcomes if o.pnl_close is not None]
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0

        win_pnls = [float(o.pnl_close) for o in outcomes if o.outcome_close == "WIN" and o.pnl_close is not None]
        loss_pnls = [float(o.pnl_close) for o in outcomes if o.outcome_close == "LOSS" and o.pnl_close is not None]
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
        avg_loss = abs(sum(loss_pnls) / len(loss_pnls)) if loss_pnls else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss) if avg_loss > 0 else 0

        sharpe = 0
        if len(pnls) > 1:
            mean_pnl = sum(pnls) / len(pnls)
            variance = sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls)
            std = variance ** 0.5
            sharpe = (mean_pnl / std) * (252 ** 0.5) if std > 0 else 0

        drawdowns = []
        peak = float("-inf")
        cumulative = 0
        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            drawdowns.append(drawdown)
        max_dd = max(drawdowns) if drawdowns else 0

        regimes = {}
        for o in outcomes:
            if o.outcome_close:
                regimes[o.outcome_close] = regimes.get(o.outcome_close, 0) + 1

        return {
            "strategy": strategy_name,
            "total_signals": total,
            "wins": wins,
            "losses": losses,
            "flats": flats,
            "timed_out": timed_out,
            "win_rate": round(win_rate, 4),
            "avg_pnl": round(avg_pnl, 6),
            "avg_win": round(avg_win, 6),
            "avg_loss": round(avg_loss, 6),
            "expectancy": round(expectancy, 6),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_dd, 6),
            "total_pnl": round(sum(pnls), 6),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
