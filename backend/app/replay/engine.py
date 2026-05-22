import enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MarketEvent
from app.strategies import get_strategy, get_strategy_names
from app.strategies.signal import StructuredSignal
from app.replay.market_state import MarketContext
from app.replay.feature_generator import FeatureGenerator
from app.services.execution_simulator import ExecutionSimulator, OrderSide, OrderbookSnapshot, FillResult


class ReplayMode(enum.Enum):
    SIGNAL_ONLY = "signal_only"
    PAPER_EXECUTION = "paper_execution"
    FULL_SIMULATION = "full_simulation"


@dataclass
class ReplayedSignal:
    strategy_name: str
    signal: StructuredSignal
    entry_timestamp: datetime
    entry_price: float | None
    feature_values: dict
    regime: str | None

    outcome_5m: str | None = None
    outcome_15m: str | None = None
    outcome_1h: str | None = None
    outcome_4h: str | None = None
    outcome_close: str | None = None

    probability_5m: float | None = None
    probability_15m: float | None = None
    probability_1h: float | None = None
    probability_4h: float | None = None
    probability_close: float | None = None

    pnl_5m: float | None = None
    pnl_15m: float | None = None
    pnl_1h: float | None = None
    pnl_4h: float | None = None
    pnl_close: float | None = None

    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    reversal_count: int = 0
    holding_time_seconds: int | None = None

    execution_slippage: float | None = None
    execution_fill_price: float | None = None
    execution_fill_size: float | None = None
    execution_partial: bool = False
    execution_spread_cost: float | None = None
    execution_latency_ms: float | None = None


@dataclass
class ReplayResult:
    strategy_name: str
    mode: ReplayMode
    start_time: datetime
    end_time: datetime
    total_events_processed: int = 0
    signals_generated: int = 0
    signals: list[ReplayedSignal] = field(default_factory=list)
    execution_summary: dict | None = None


class PendingOutcome:
    def __init__(self, signal: ReplayedSignal):
        self.signal = signal
        self.entry_price = signal.entry_price
        self.entry_timestamp = signal.entry_timestamp
        self.checkpoints = {
            "5m": signal.entry_timestamp + timedelta(minutes=5),
            "15m": signal.entry_timestamp + timedelta(minutes=15),
            "1h": signal.entry_timestamp + timedelta(hours=1),
            "4h": signal.entry_timestamp + timedelta(hours=4),
        }
        self.checkpoints_met: set[str] = set()

    def evaluate(self, current_timestamp: datetime, current_price: float, signal_direction: str):
        if self.entry_price is None or current_price is None:
            return

        price_change = current_price - self.entry_price
        if signal_direction == "BUY_YES":
            movement = price_change
        elif signal_direction == "BUY_NO":
            movement = -price_change
        else:
            movement = 0.0

        if movement > 0:
            self.signal.max_favorable_excursion = max(self.signal.max_favorable_excursion, abs(movement))
        else:
            self.signal.max_adverse_excursion = max(self.signal.max_adverse_excursion, abs(movement))

        for label, deadline in self.checkpoints.items():
            if label in self.checkpoints_met:
                continue
            if current_timestamp >= deadline:
                self.checkpoints_met.add(label)
                win = movement > 0.001 * self.entry_price
                loss = movement < -0.001 * self.entry_price
                setattr(self.signal, f"outcome_{label}", "WIN" if win else "LOSS" if loss else "FLAT")
                setattr(self.signal, f"probability_{label}", current_price)
                setattr(self.signal, f"pnl_{label}", movement)

    @property
    def is_finalized(self) -> bool:
        return len(self.checkpoints_met) >= len(self.checkpoints)


class ReplayEngine:
    def __init__(self, db: AsyncSession, execution_simulator: ExecutionSimulator | None = None):
        self.db = db
        self.feature_generator = FeatureGenerator()
        self.whale_threshold = 500
        self.execution_simulator = execution_simulator or ExecutionSimulator()

    async def run(
        self,
        strategy_name: str,
        start_time: datetime,
        end_time: datetime | None = None,
        mode: ReplayMode = ReplayMode.SIGNAL_ONLY,
        market_ids: list[str] | None = None,
        config: dict | None = None,
        signal_interval_seconds: int = 300,
    ) -> ReplayResult:
        if end_time is None:
            end_time = datetime.now(timezone.utc)

        strategy = get_strategy(strategy_name, config=config)
        result = ReplayResult(
            strategy_name=strategy_name,
            mode=mode,
            start_time=start_time,
            end_time=end_time,
        )

        events = await self._load_events(start_time, end_time, market_ids)
        result.total_events_processed = len(events)

        contexts: dict[str, MarketContext] = {}
        last_signal_time: dict[str, datetime] = {}
        pending_outcomes: list[PendingOutcome] = []

        for event in events:
            cid = event.market.condition_id if event.market else str(event.market_id)
            if cid not in contexts:
                contexts[cid] = MarketContext(condition_id=cid, market_id=str(event.market_id or ""))

            ctx = contexts[cid]

            price = float(event.price) if event.price else ctx.current_price
            size = float(event.size) if event.size else 0.0
            side = event.outcome or "buy"
            maker = event.maker_address
            taker = event.taker_address

            if event.event_type == "trade" and price:
                ctx.update_trade(event.timestamp, price, size, side, maker, taker)

            ts = event.timestamp.replace(tzinfo=timezone.utc) if event.timestamp.tzinfo is None else event.timestamp

            should_signal = (
                strategy.config.enabled
                and cid not in last_signal_time
                or (ts - last_signal_time.get(cid, datetime.min.replace(tzinfo=timezone.utc))).total_seconds() >= signal_interval_seconds
            )

            if should_signal and ctx.current_price is not None:
                features = self.feature_generator.generate(ctx)
                features["market_id"] = ctx.market_id
                features["condition_id"] = ctx.condition_id

                market_state = {
                    **features,
                    "wallet": taker or maker or "",
                    "size": size,
                    "side": side,
                    "wallet_score": 0.65,
                    "recency_hours": 0,
                }

                try:
                    signal = await strategy.generate_signal(market_state)
                    if signal is not None:
                        last_signal_time[cid] = ts

                        fill_price = ctx.current_price
                        fill_size = size
                        slippage = 0.0
                        partial = False
                        spread_cost = 0.0

                        if mode != ReplayMode.SIGNAL_ONLY:
                            order_side = OrderSide.BUY if signal.signal == "BUY_YES" else OrderSide.SELL
                            ob = OrderbookSnapshot.from_liquidity(ctx.current_price, ctx.volume_window_1h or 10000)
                            fill = self.execution_simulator.simulate_market_order(order_side, size, orderbook=ob)
                            fill_price = fill.avg_fill_price
                            fill_size = fill.filled_size
                            slippage = fill.slippage
                            partial = fill.partial
                            spread_cost = fill.spread_cost

                        replayed = ReplayedSignal(
                            strategy_name=strategy_name,
                            signal=signal,
                            entry_timestamp=ts,
                            entry_price=fill_price,
                            feature_values=features,
                            regime=ctx.get_regime(),
                            execution_slippage=slippage,
                            execution_fill_price=fill_price,
                            execution_fill_size=fill_size,
                            execution_partial=partial,
                            execution_spread_cost=spread_cost,
                        )
                        result.signals.append(replayed)
                        result.signals_generated += 1
                        pending_outcomes.append(PendingOutcome(replayed))
                except Exception:
                    pass

            still_pending = []
            for po in pending_outcomes:
                if po.entry_price is not None and ctx.current_price is not None:
                    po.evaluate(ts, ctx.current_price, po.signal.signal)
                if not po.is_finalized:
                    still_pending.append(po)
            pending_outcomes = still_pending

        for po in pending_outcomes:
            if po.entry_price is not None and ctx.current_price is not None:
                po.evaluate(ts, ctx.current_price, po.signal.signal)
                po.signal.outcome_close = po.signal.outcome_1h or po.signal.outcome_15m or "TIMEOUT"
                prob_close = po.signal.probability_1h or po.signal.probability_15m or ctx.current_price
                po.signal.probability_close = prob_close
                price_change = prob_close - po.entry_price
                if po.signal.signal == "BUY_NO":
                    price_change = -price_change
                po.signal.pnl_close = price_change

        return result

    async def run_multi(
        self,
        strategy_names: list[str] | None = None,
        start_time: datetime = datetime.now(timezone.utc) - timedelta(days=7),
        end_time: datetime | None = None,
        mode: ReplayMode = ReplayMode.SIGNAL_ONLY,
        market_ids: list[str] | None = None,
    ) -> dict[str, ReplayResult]:
        if strategy_names is None:
            strategy_names = get_strategy_names()
        results = {}
        for name in strategy_names:
            results[name] = await self.run(
                strategy_name=name,
                start_time=start_time,
                end_time=end_time,
                mode=mode,
                market_ids=market_ids,
            )
        return results

    async def _load_events(self, start_time: datetime, end_time: datetime, market_ids: list[str] | None):
        from sqlalchemy.orm import selectinload
        query = (
            select(MarketEvent)
            .options(selectinload(MarketEvent.market))
            .where(MarketEvent.timestamp.between(start_time, end_time))
            .order_by(MarketEvent.timestamp)
        )

        if market_ids:
            from app.models import Market
            subq = select(Market.id).where(Market.condition_id.in_(market_ids))
            query = query.where(MarketEvent.market_id.in_(subq))

        result = await self.db.execute(query)
        return list(result.scalars().all())
