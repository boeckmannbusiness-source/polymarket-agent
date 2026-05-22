import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class OrderbookLevel:
    price: float
    size: float
    order_count: int = 1


@dataclass
class FillResult:
    filled_size: float
    avg_fill_price: float
    slippage: float
    spread_cost: float
    partial: bool
    remaining_size: float
    queue_position: float
    fill_events: list[dict] = field(default_factory=list)


@dataclass
class OrderbookSnapshot:
    bids: list[OrderbookLevel] = field(default_factory=list)
    asks: list[OrderbookLevel] = field(default_factory=list)
    mid_price: float = 0.5
    spread: float = 0.01
    liquidity_depth: float = 10000.0

    @classmethod
    def from_liquidity(cls, mid_price: float, liquidity: float, spread: float | None = None) -> "OrderbookSnapshot":
        if spread is None:
            spread = 0.5 / liquidity if liquidity > 0 else 0.02
        spread = max(spread, 0.001)
        half_spread = spread / 2
        bid_price = mid_price * (1 - half_spread)
        ask_price = mid_price * (1 + half_spread)
        depth = liquidity * 0.1
        levels = 5
        asks = []
        bids = []
        for i in range(levels):
            decay = math.exp(-i * 0.5)
            asks.append(OrderbookLevel(price=ask_price * (1 + i * 0.005), size=depth * decay, order_count=max(1, int(decay * 10))))
            bids.append(OrderbookLevel(price=bid_price * (1 - i * 0.005), size=depth * decay, order_count=max(1, int(decay * 10))))
        return cls(bids=bids, asks=asks, mid_price=mid_price, spread=spread, liquidity_depth=liquidity)


class ExecutionSimulator:
    def __init__(self, latency_ms: float = 50.0, fill_ratio: float = 0.95):
        self.latency_ms = latency_ms
        self.fill_ratio = fill_ratio

    def simulate_market_order(
        self,
        side: OrderSide,
        size: float,
        orderbook: OrderbookSnapshot | None = None,
        mid_price: float | None = None,
        liquidity: float | None = None,
    ) -> FillResult:
        if orderbook is None:
            mp = mid_price if mid_price is not None else 0.5
            liq = liquidity if liquidity is not None else 10000.0
            orderbook = OrderbookSnapshot.from_liquidity(mp, liq)

        levels = orderbook.asks if side == OrderSide.BUY else orderbook.bids
        if not levels:
            mp = orderbook.mid_price
            spread = orderbook.spread
            base_price = mp * (1 + spread / 2) if side == OrderSide.BUY else mp * (1 - spread / 2)
            return FillResult(
                filled_size=0.0, avg_fill_price=base_price, slippage=0.0,
                spread_cost=spread, partial=True, remaining_size=size,
                queue_position=0.5, fill_events=[],
            )

        remaining = size
        total_cost = 0.0
        total_filled = 0.0
        fill_events = []
        queue_pos = random.uniform(0.3, 0.8)

        for level in levels:
            if remaining <= 0:
                break
            available = level.size * (1.0 if queue_pos <= 0.5 else 0.7)
            fill = min(remaining, available)
            fill_ratio = fill / available
            queue_wait = queue_pos / (1.0 + random.random())
            partial = fill < remaining and fill < available
            fill_events.append({
                "price": level.price,
                "size": fill,
                "fill_ratio": fill_ratio,
                "queue_position": queue_pos,
                "queue_wait_ms": queue_wait * 100,
            })
            total_cost += fill * level.price
            total_filled += fill
            remaining -= fill

        if total_filled == 0:
            base_price = levels[0].price if levels else orderbook.mid_price
            return FillResult(
                filled_size=0.0, avg_fill_price=base_price,
                slippage=0.0, spread_cost=orderbook.spread,
                partial=True, remaining_size=size,
                queue_position=queue_pos, fill_events=[],
            )

        avg_price = total_cost / total_filled
        mp = orderbook.mid_price
        if side == OrderSide.BUY:
            slippage = (avg_price - mp) / mp
            spread_cost = (avg_price - mp) * total_filled
        else:
            slippage = (mp - avg_price) / mp
            spread_cost = (mp - avg_price) * total_filled

        return FillResult(
            filled_size=total_filled,
            avg_fill_price=avg_price,
            slippage=slippage,
            spread_cost=spread_cost,
            partial=remaining > 0,
            remaining_size=remaining,
            queue_position=queue_pos,
            fill_events=fill_events,
        )

    def estimate_slippage(self, size: float, liquidity: float, mid_price: float = 0.5) -> float:
        if liquidity <= 0 or size <= 0:
            return 0.01
        impact = size / liquidity
        base_slippage = 0.001
        slippage = base_slippage + impact * 0.5
        return min(slippage, 0.1)

    def simulate_partial_fill(self, size: float, liquidity: float) -> tuple[float, float]:
        fill_prob = min(1.0, liquidity / (size * 10))
        if random.random() > self.fill_ratio * fill_prob:
            filled = size * random.uniform(0.3, 0.9)
            return filled, size - filled
        return size, 0.0
