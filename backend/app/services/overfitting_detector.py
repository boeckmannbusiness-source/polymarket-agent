from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade
from app.core.logging import logger


@dataclass
class OverfitScore:
    score: float
    reason: str
    risk_level: str  # "LOW" | "MEDIUM" | "HIGH"


class OverfittingDetector:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect(self, strategy_name: str) -> OverfitScore:
        signals = []
        reasons = []

        zn = await self._check_narrow_price_zone(strategy_name)
        signals.append(zn)

        rd = await self._check_regime_dependence(strategy_name)
        signals.append(rd)

        hv = await self._check_high_variance_expectancy(strategy_name)
        signals.append(hv)

        cd = await self._check_window_collapse(strategy_name)
        signals.append(cd)

        rd_resid = await self._check_residual_dominance(strategy_name)
        signals.append(rd_resid)

        score = sum(s["score"] for s in signals) / max(len(signals), 1)
        contributing = [s for s in signals if s["score"] > 0.2]
        if contributing:
            reasons.extend(s["reason"] for s in contributing)

        if score >= 0.6:
            risk = "HIGH"
        elif score >= 0.3:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        return OverfitScore(
            score=round(score, 4),
            reason="; ".join(reasons) if reasons else "no_overfitting_signals_detected",
            risk_level=risk,
        )

    async def _check_narrow_price_zone(self, strategy_name: str) -> dict[str, Any]:
        trades = await self._fetch_trades(strategy_name, days=60)
        if len(trades) < 10:
            return {"score": 0.0, "reason": "insufficient_trades"}

        zones: dict[str, int] = {}
        for t in trades:
            price = float(t.filled_price or t.price or 0.5)
            zone = self._classify_price_zone(price)
            zones[zone] = zones.get(zone, 0) + 1

        if not zones:
            return {"score": 0.0, "reason": "no_price_data"}

        dominant_zone_count = max(zones.values())
        dominance_ratio = dominant_zone_count / len(trades)

        if dominance_ratio > 0.9:
            dominant_zone = max(zones, key=zones.get)
            return {"score": 0.8, "reason": f"performance_only_in_{dominant_zone}_({dominance_ratio:.0%}_dominance)"}
        elif dominance_ratio > 0.7:
            return {"score": 0.4, "reason": f"narrow_price_zone_dominance_{dominance_ratio:.0%}"}
        return {"score": 0.0, "reason": "diverse_price_zones"}

    async def _check_regime_dependence(self, strategy_name: str) -> dict[str, Any]:
        from app.models.market_snapshot import MarketStateSnapshot

        trades = await self._fetch_trades(strategy_name, days=60)
        if len(trades) < 10:
            return {"score": 0.0, "reason": "insufficient_trades"}

        regime_pnls: dict[str, list[float]] = {}
        for t in trades:
            snap = await self.db.execute(
                select(MarketStateSnapshot.regime)
                .where(MarketStateSnapshot.condition_id.isnot(None))
                .order_by(MarketStateSnapshot.timestamp.desc())
                .limit(1)
            )
            snap_row = snap.scalar_one_or_none()
            regime = snap_row if snap_row else "unknown"
            if regime not in regime_pnls:
                regime_pnls[regime] = []
            regime_pnls[regime].append(float(t.pnl or 0))

        if len(regime_pnls) < 2:
            return {"score": 0.3, "reason": "single_regime_dominance"}

        regime_means = {}
        for regime, pnls in regime_pnls.items():
            regime_means[regime] = sum(pnls) / len(pnls) if pnls else 0

        if not regime_means:
            return {"score": 0.0, "reason": "no_regime_data"}

        top_regime = max(regime_means, key=regime_means.get)
        top_mean = regime_means[top_regime]
        other_means = [v for k, v in regime_means.items() if k != top_regime]
        avg_other = sum(other_means) / len(other_means) if other_means else 0

        if top_mean > 0 and avg_other <= 0:
            return {"score": 0.7, "reason": f"edge_only_in_{top_regime}_regime"}
        elif top_mean > 0 and avg_other > 0:
            return {"score": 0.2, "reason": "edge_persists_across_regimes"}
        return {"score": 0.0, "reason": "no_regime_spike"}

    async def _check_high_variance_expectancy(self, strategy_name: str) -> dict[str, Any]:
        trades = await self._fetch_trades(strategy_name, days=60)
        if len(trades) < 20:
            return {"score": 0.0, "reason": "insufficient_trades"}

        chunk_size = max(1, len(trades) // 3)
        chunks = [trades[i:i + chunk_size] for i in range(0, len(trades), chunk_size)]
        chunk_expectancies = []
        for chunk in chunks:
            if chunk:
                chunk_expectancies.append(sum(float(t.pnl or 0) for t in chunk) / len(chunk))

        if len(chunk_expectancies) < 2:
            return {"score": 0.0, "reason": "too_few_chunks"}

        mean_exp = sum(chunk_expectancies) / len(chunk_expectancies)
        variance = sum((e - mean_exp) ** 2 for e in chunk_expectancies) / len(chunk_expectancies)
        cv = (variance ** 0.5) / (abs(mean_exp) + 0.001)

        if cv > 2.0:
            return {"score": 0.7, "reason": f"high_expectancy_variance_cv={cv:.2f}"}
        elif cv > 1.0:
            return {"score": 0.4, "reason": f"moderate_expectancy_variance_cv={cv:.2f}"}
        return {"score": 0.0, "reason": f"stable_expectancy_cv={cv:.2f}"}

    async def _check_window_collapse(self, strategy_name: str) -> dict[str, Any]:
        trades_7d = await self._fetch_trades(strategy_name, days=7)
        trades_30d = await self._fetch_trades(strategy_name, days=30)
        trades_60d = await self._fetch_trades(strategy_name, days=60)

        if len(trades_7d) < 5 or len(trades_30d) < 10:
            return {"score": 0.0, "reason": "insufficient_window_data"}

        exp_7d = sum(float(t.pnl or 0) for t in trades_7d) / len(trades_7d) if trades_7d else 0
        exp_30d = sum(float(t.pnl or 0) for t in trades_30d) / len(trades_30d) if trades_30d else 0
        exp_60d = sum(float(t.pnl or 0) for t in trades_60d) if trades_60d else 0
        exp_60d = exp_60d / len(trades_60d) if trades_60d else 0

        if exp_7d < 0 and exp_30d > 0 and exp_60d > 0:
            return {"score": 0.3, "reason": "recent_7d_performance_collapse"}
        if exp_7d < 0 and exp_30d < 0 and exp_60d > 0:
            return {"score": 0.6, "reason": "performance_collapses_outside_30d_window"}
        if exp_7d < 0 and exp_30d < 0 and exp_60d < 0:
            return {"score": 0.0, "reason": "consistent_negative_performance"}
        return {"score": 0.0, "reason": "consistent_window_performance"}

    async def _check_residual_dominance(self, strategy_name: str) -> dict[str, Any]:
        trades = await self._fetch_trades(strategy_name, days=60)
        if len(trades) < 10:
            return {"score": 0.0, "reason": "insufficient_trades"}

        pnls = [float(t.pnl or 0) for t in trades]
        total_abs_pnl = sum(abs(p) for p in pnls)
        if total_abs_pnl == 0:
            return {"score": 0.0, "reason": "zero_pnl"}

        sorted_pnls = sorted(pnls, reverse=True)
        top_n = max(1, len(sorted_pnls) // 10)
        top_pnl_sum = sum(p for p in sorted_pnls[:top_n] if p > 0)
        residual_ratio = top_pnl_sum / total_abs_pnl if total_abs_pnl > 0 else 0

        if residual_ratio > 0.9:
            return {"score": 0.8, "reason": f"residual_dominance_{residual_ratio:.0%}_top_10%_trades"}
        elif residual_ratio > 0.7:
            return {"score": 0.5, "reason": f"moderate_residual_dominance_{residual_ratio:.0%}"}
        return {"score": 0.0, "reason": f"balanced_residuals_{residual_ratio:.0%}"}

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

    async def _fetch_trades(self, strategy_name: str, days: int) -> list[Trade]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(Trade)
            .where(
                Trade.agent_id == strategy_name,
                Trade.status == "closed",
                Trade.exit_timestamp >= cutoff,
                Trade.pnl.isnot(None),
            )
            .order_by(Trade.exit_timestamp.asc())
        )
        return list(result.scalars().all())
