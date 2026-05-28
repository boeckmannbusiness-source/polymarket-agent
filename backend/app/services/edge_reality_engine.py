from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade, Market, MarketEvent
from app.core.logging import logger


@dataclass
class EdgeReport:
    expectancy: float
    sharpe_proxy: float
    stability_score: float
    tail_risk: float
    confidence_score: float
    win_rate: float = 0.0
    loss_severity: float = 0.0
    total_trades: int = 0
    expectancy_per_regime: dict[str, float] = field(default_factory=dict)
    expectancy_per_price_zone: dict[str, float] = field(default_factory=dict)
    expectancy_per_archetype: dict[str, float] = field(default_factory=dict)
    expectancy_per_resolution: dict[str, float] = field(default_factory=dict)


class EdgeRealityEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_edge(
        self, strategy_name: str | None = None, days: int = 30
    ) -> EdgeReport:
        trades = await self._fetch_closed_trades(strategy_name, days)
        if not trades:
            return EdgeReport(
                expectancy=0.0, sharpe_proxy=0.0, stability_score=0.0,
                tail_risk=0.0, confidence_score=0.0, total_trades=0,
            )

        pnls = [float(t.pnl or 0) for t in trades]
        costs = [self._estimate_cost(t) for t in trades]
        net_pnls = [p - c for p, c in zip(pnls, costs)]

        expectancy = sum(net_pnls) / len(net_pnls) if net_pnls else 0.0

        winning = [p for p in net_pnls if p > 0]
        losing = [p for p in net_pnls if p <= 0]
        win_rate = len(winning) / len(net_pnls) if net_pnls else 0.0
        loss_severity = abs(sum(losing) / len(losing)) if losing else 0.0

        mean = sum(net_pnls) / len(net_pnls) if net_pnls else 0
        variance = sum((p - mean) ** 2 for p in net_pnls) / len(net_pnls) if net_pnls else 1
        std = variance ** 0.5 or 0.0001
        sharpe_proxy = mean / std

        sorted_pnls = sorted(net_pnls)
        tail_idx = max(1, int(len(sorted_pnls) * 0.05))
        tail_returns = sorted_pnls[:tail_idx]
        tail_risk = abs(sum(tail_returns) / len(tail_returns)) if tail_returns else 0.0

        stability_score = self._compute_stability(net_pnls)

        confidence_score = min(1.0, (win_rate * 0.4 + (1.0 - loss_severity / (abs(mean) + loss_severity + 0.001)) * 0.3 + stability_score * 0.3))

        regime_edge = await self._compute_edge_per_regime(strategy_name, days)
        price_zone_edge = await self._compute_edge_per_price_zone(strategy_name, days)
        archetype_edge = await self._compute_edge_per_archetype(strategy_name, days)
        resolution_edge = await self._compute_edge_per_resolution(strategy_name, days)

        return EdgeReport(
            expectancy=round(expectancy, 6),
            sharpe_proxy=round(sharpe_proxy, 6),
            stability_score=round(stability_score, 6),
            tail_risk=round(tail_risk, 6),
            confidence_score=round(confidence_score, 6),
            win_rate=round(win_rate, 6),
            loss_severity=round(loss_severity, 6),
            total_trades=len(trades),
            expectancy_per_regime=regime_edge,
            expectancy_per_price_zone=price_zone_edge,
            expectancy_per_archetype=archetype_edge,
            expectancy_per_resolution=resolution_edge,
        )

    def _estimate_cost(self, trade: Trade) -> float:
        slippage = float(trade.slippage or 0.001)
        fee = float(trade.fee or 0)
        return slippage * float(trade.filled_size or trade.size or 0) + fee

    def _compute_stability(self, pnls: list[float]) -> float:
        if len(pnls) < 5:
            return 0.5
        chunk_size = max(1, len(pnls) // 5)
        chunks = [pnls[i:i + chunk_size] for i in range(0, len(pnls), chunk_size)]
        chunk_means = [sum(c) / len(c) for c in chunks if c]
        if len(chunk_means) < 2:
            return 0.5
        mean_var = sum((m - sum(chunk_means) / len(chunk_means)) ** 2 for m in chunk_means) / len(chunk_means)
        return max(0, 1.0 - min(1.0, mean_var / (abs(sum(chunk_means) / len(chunk_means)) + 0.001)))

    async def _fetch_closed_trades(self, strategy_name: str | None, days: int) -> list[Trade]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = select(Trade).where(
            Trade.status == "closed",
            Trade.exit_timestamp >= cutoff,
            Trade.pnl.isnot(None),
        )
        if strategy_name:
            query = query.where(Trade.agent_id == strategy_name)
        query = query.order_by(Trade.exit_timestamp.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _fetch_trades_for_analysis(
        self, strategy_name: str | None, days: int
    ) -> list[dict[str, Any]]:
        trades = await self._fetch_closed_trades(strategy_name, days)
        result = []
        for t in trades:
            pnl = float(t.pnl or 0)
            cost = self._estimate_cost(t)
            net = pnl - cost
            result.append({
                "trade_id": str(t.id),
                "market_id": t.market_id,
                "strategy": t.agent_id,
                "side": t.side,
                "outcome": t.outcome,
                "pnl": pnl,
                "cost": cost,
                "net_pnl": net,
                "entry_price": float(t.filled_price or t.price or 0.5),
                "exit_timestamp": t.exit_timestamp,
                "entry_timestamp": t.entry_timestamp,
            })
        return result

    async def _compute_edge_per_regime(self, strategy_name: str | None, days: int) -> dict[str, float]:
        from app.models.portfolio import PortfolioSnapshot
        from app.models.market_snapshot import MarketStateSnapshot

        trades = await self._fetch_trades_for_analysis(strategy_name, days)
        if not trades:
            return {}

        regime_net_pnls: dict[str, list[float]] = {}
        for t in trades:
            if not t["exit_timestamp"]:
                continue
            snapshot = await self.db.execute(
                select(MarketStateSnapshot)
                .where(MarketStateSnapshot.condition_id.isnot(None))
                .order_by(MarketStateSnapshot.timestamp.desc())
                .limit(1)
            )
            snap = snapshot.scalar_one_or_none()
            regime = snap.regime if snap and snap.regime else "unknown"
            if regime not in regime_net_pnls:
                regime_net_pnls[regime] = []
            regime_net_pnls[regime].append(t["net_pnl"])

        result = {}
        for regime, net_pnls in regime_net_pnls.items():
            result[regime] = round(sum(net_pnls) / len(net_pnls), 6) if net_pnls else 0.0
        return result

    async def _compute_edge_per_price_zone(self, strategy_name: str | None, days: int) -> dict[str, float]:
        trades = await self._fetch_trades_for_analysis(strategy_name, days)
        if not trades:
            return {}

        zone_net_pnls: dict[str, list[float]] = {}
        for t in trades:
            price = t["entry_price"]
            zone = self._classify_price_zone(price)
            if zone not in zone_net_pnls:
                zone_net_pnls[zone] = []
            zone_net_pnls[zone].append(t["net_pnl"])

        result = {}
        for zone, net_pnls in zone_net_pnls.items():
            result[zone] = round(sum(net_pnls) / len(net_pnls), 6) if net_pnls else 0.0
        return result

    def _classify_price_zone(self, price: float) -> str:
        if price <= 0.2:
            return "crisis_zone"
        elif price <= 0.4:
            return "low_probability"
        elif price <= 0.6:
            return "fair_value"
        elif price <= 0.8:
            return "high_probability"
        else:
            return "extreme_zone"

    async def _compute_edge_per_archetype(self, strategy_name: str | None, days: int) -> dict[str, float]:
        trades = await self._fetch_trades_for_analysis(strategy_name, days)
        if not trades:
            return {}

        archetype_net_pnls: dict[str, list[float]] = {}
        for t in trades:
            archetype = await self._detect_market_archetype(t["market_id"])
            if not archetype:
                archetype = "unknown"
            if archetype not in archetype_net_pnls:
                archetype_net_pnls[archetype] = []
            archetype_net_pnls[archetype].append(t["net_pnl"])

        result = {}
        for archetype, net_pnls in archetype_net_pnls.items():
            result[archetype] = round(sum(net_pnls) / len(net_pnls), 6) if net_pnls else 0.0
        return result

    async def _detect_market_archetype(self, market_id) -> str:
        if not market_id:
            return "unknown"
        result = await self.db.execute(
            select(Market.volume, Market.liquidity)
            .where(Market.id == market_id)
        )
        row = result.one_or_none()
        if not row:
            return "unknown"
        volume = float(row[0] or 0)
        liquidity = float(row[1] or 0)
        if volume > 1_000_000 or liquidity > 500_000:
            return "high_liquidity"
        elif volume > 100_000 or liquidity > 50_000:
            return "medium_liquidity"
        elif volume > 10_000:
            return "low_liquidity"
        else:
            return "illiquid"

    async def _compute_edge_per_resolution(self, strategy_name: str | None, days: int) -> dict[str, float]:
        trades = await self._fetch_trades_for_analysis(strategy_name, days)
        if not trades:
            return {}

        resolution_net_pnls: dict[str, list[float]] = {}
        for t in trades:
            if not t["entry_timestamp"] or not t["exit_timestamp"]:
                continue
            holding = (t["exit_timestamp"] - t["entry_timestamp"]).total_seconds()
            resolution = self._classify_resolution(holding)
            if resolution not in resolution_net_pnls:
                resolution_net_pnls[resolution] = []
            resolution_net_pnls[resolution].append(t["net_pnl"])

        result = {}
        for resolution, net_pnls in resolution_net_pnls.items():
            result[resolution] = round(sum(net_pnls) / len(net_pnls), 6) if net_pnls else 0.0
        return result

    def _classify_resolution(self, holding_seconds: float) -> str:
        if holding_seconds < 300:
            return "scalp"
        elif holding_seconds < 3600:
            return "intraday"
        elif holding_seconds < 86400:
            return "swing"
        elif holding_seconds < 604800:
            return "position"
        else:
            return "long_term"
