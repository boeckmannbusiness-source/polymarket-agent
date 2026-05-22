import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MarketEvent, MarketStateSnapshot


@dataclass
class RegimeProbabilities:
    high_volatility: float = 0.0
    low_volatility: float = 0.0
    momentum: float = 0.0
    mean_reverting: float = 0.0
    illiquid: float = 0.0
    normal: float = 0.0

    @property
    def dominant(self) -> str:
        probs = {
            "high_volatility": self.high_volatility,
            "low_volatility": self.low_volatility,
            "momentum": self.momentum,
            "mean_reverting": self.mean_reverting,
            "illiquid": self.illiquid,
            "normal": self.normal,
        }
        return max(probs, key=probs.get)

    @property
    def confidence(self) -> float:
        probs = [self.high_volatility, self.low_volatility, self.momentum,
                 self.mean_reverting, self.illiquid, self.normal]
        sorted_probs = sorted(probs, reverse=True)
        if sum(probs) == 0:
            return 0.0
        return sorted_probs[0] / sum(probs)

    def to_dict(self) -> dict:
        return {
            "high_volatility": round(self.high_volatility, 4),
            "low_volatility": round(self.low_volatility, 4),
            "momentum": round(self.momentum, 4),
            "mean_reverting": round(self.mean_reverting, 4),
            "illiquid": round(self.illiquid, 4),
            "normal": round(self.normal, 4),
            "dominant": self.dominant,
            "confidence": round(self.confidence, 4),
        }


class RegimeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def classify(self, market_condition_id: str | None = None) -> RegimeProbabilities:
        probs = RegimeProbabilities()

        if market_condition_id:
            result = await self.db.execute(
                select(MarketStateSnapshot)
                .where(MarketStateSnapshot.condition_id == market_condition_id)
                .order_by(MarketStateSnapshot.timestamp.desc())
                .limit(10)
            )
            snapshots = list(result.scalars().all())
        else:
            result = await self.db.execute(
                select(MarketStateSnapshot)
                .order_by(MarketStateSnapshot.timestamp.desc())
                .limit(50)
            )
            snapshots = list(result.scalars().all())

        if not snapshots:
            return self._classify_from_scratch(market_condition_id)

        return self._classify_from_snapshots(snapshots)

    async def _classify_from_scratch(self, market_condition_id: str | None = None) -> RegimeProbabilities:
        probs = RegimeProbabilities()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)

        query = select(MarketEvent)
        if market_condition_id:
            from app.models import Market
            subq = select(Market.id).where(Market.condition_id == market_condition_id)
            query = query.where(MarketEvent.market_id.in_(subq))
        query = query.where(MarketEvent.timestamp >= cutoff).order_by(MarketEvent.timestamp)

        result = await self.db.execute(query)
        events = list(result.scalars().all())

        if len(events) < 5:
            probs.normal = 0.6
            probs.illiquid = 0.3
            probs.low_volatility = 0.1
            return probs

        prices = [float(e.price) for e in events if e.price]
        volumes = [float(e.size) for e in events if e.size]

        if len(prices) < 3:
            probs.normal = 0.6
            probs.illiquid = 0.3
            probs.low_volatility = 0.1
            return probs

        mean_price = sum(prices) / len(prices)
        variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
        std = math.sqrt(variance)
        vol_ratio = std / mean_price if mean_price > 0 else 0

        total_volume = sum(volumes)
        avg_trade_size = total_volume / len(volumes) if volumes else 0
        whale_ratio = sum(1 for v in volumes if v >= 500) / len(volumes) if volumes else 0

        momentum_val = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
        abs_momentum = abs(momentum_val)

        probs.high_volatility = self._sigmoid(vol_ratio, 0.08, 10)
        probs.low_volatility = 1.0 - self._sigmoid(vol_ratio, 0.03, 15)
        probs.illiquid = max(0, 1.0 - min(1.0, total_volume / 50000))
        probs.momentum = self._sigmoid(abs_momentum, 0.04, 15) * (1.0 - probs.illiquid)
        probs.mean_reverting = max(0, (1.0 - abs_momentum * 10) * (1.0 - probs.momentum))
        probs.normal = max(0, 1.0 - sum([
            probs.high_volatility, probs.low_volatility,
            probs.momentum, probs.mean_reverting, probs.illiquid,
        ]))

        total = sum(v for v in probs.__dict__.values() if isinstance(v, (int, float)))
        if total > 0:
            for key in ["high_volatility", "low_volatility", "momentum",
                        "mean_reverting", "illiquid", "normal"]:
                setattr(probs, key, getattr(probs, key) / total)

        return probs

    def _classify_from_snapshots(self, snapshots: list) -> RegimeProbabilities:
        probs = RegimeProbabilities()
        recent = snapshots[:5]
        regimes = [s.regime for s in recent if s.regime]

        if not regimes:
            probs.normal = 1.0
            return probs

        for regime in regimes:
            if regime == "high_volatility":
                probs.high_volatility += 1
            elif regime == "low_volatility":
                probs.low_volatility += 1
            elif regime == "momentum":
                probs.momentum += 1
            elif regime == "mean_reverting":
                probs.mean_reverting += 1
            elif regime == "illiquid":
                probs.illiquid += 1
            else:
                probs.normal += 1

        total = sum([probs.high_volatility, probs.low_volatility, probs.momentum,
                     probs.mean_reverting, probs.illiquid, probs.normal])
        if total > 0:
            for key in ["high_volatility", "low_volatility", "momentum",
                        "mean_reverting", "illiquid", "normal"]:
                setattr(probs, key, getattr(probs, key) / total)

        return probs

    def _sigmoid(self, x: float, midpoint: float, steepness: float = 10) -> float:
        return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))
