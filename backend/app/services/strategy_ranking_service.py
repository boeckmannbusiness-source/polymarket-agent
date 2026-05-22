import math
from datetime import datetime, timezone
from collections import defaultdict

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SignalOutcome, MarketStateSnapshot
from app.strategies import get_strategy_names


class StrategyRankingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def rank_strategies(self) -> list[dict]:
        names = get_strategy_names()
        rankings = []

        for name in names:
            try:
                summary = await self._compute_strategy_score(name)
                rankings.append(summary)
            except Exception:
                continue

        rankings.sort(key=lambda r: r.get("composite_score", 0) or 0, reverse=True)
        return rankings

    async def _compute_strategy_score(self, strategy_name: str) -> dict:
        result = await self.db.execute(
            select(SignalOutcome)
            .where(SignalOutcome.strategy_name == strategy_name)
            .order_by(desc(SignalOutcome.entry_timestamp))
            .limit(500)
        )
        outcomes = list(result.scalars().all())
        total = len(outcomes)

        if total == 0:
            return {"strategy": strategy_name, "total_signals": 0, "composite_score": 0.0}

        wins = sum(1 for o in outcomes if o.outcome_close == "WIN")
        losses = sum(1 for o in outcomes if o.outcome_close == "LOSS")
        flats = sum(1 for o in outcomes if o.outcome_close == "FLAT")
        timed_out = total - wins - losses - flats
        executed = wins + losses
        win_rate = wins / executed if executed > 0 else 0

        pnls = [float(o.pnl_close or 0) for o in outcomes if o.pnl_close is not None]
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0

        win_pnls = [float(o.pnl_close or 0) for o in outcomes if o.outcome_close == "WIN"]
        loss_pnls = [float(o.pnl_close or 0) for o in outcomes if o.outcome_close == "LOSS"]
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
        avg_loss = abs(sum(loss_pnls) / len(loss_pnls)) if loss_pnls else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss) if avg_loss > 0 else avg_pnl

        sharpe = 0.0
        if len(pnls) > 1:
            mean_pnl = sum(pnls) / len(pnls)
            variance = sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls)
            std = variance ** 0.5
            sharpe = (mean_pnl / std) * (252 ** 0.5) if std > 0 else 0

        drawdowns = []
        peak = float("-inf")
        cumulative = 0.0
        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            drawdowns.append(peak - cumulative)
        max_dd = max(drawdowns) if drawdowns else 0.0
        calmar = abs(avg_pnl * total / max_dd) if max_dd > 0 else 0

        consistency = 0.0
        if len(pnls) > 1:
            mean_pnl = sum(pnls) / len(pnls)
            consistency = 1.0 - (math.sqrt(sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls)) / abs(mean_pnl)) if mean_pnl != 0 else 0

        regimes = defaultdict(lambda: {"wins": 0, "total": 0})
        for o in outcomes:
            pass
        regime_stability = 0.0

        expectancy_score = min(expectancy / 0.01, 10.0) if expectancy > 0 else max(expectancy / 0.01, -5.0)
        sharpe_score = max(0, min(sharpe / 2.0, 5.0))
        calmar_score = min(calmar * 0.1, 5.0)
        consistency_score = max(0, consistency * 3.0)
        volume_score = min(total / 50.0, 3.0)

        composite = (
            expectancy_score * 0.30
            + sharpe_score * 0.25
            + calmar_score * 0.15
            + consistency_score * 0.15
            + volume_score * 0.15
        )

        return {
            "strategy": strategy_name,
            "total_signals": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 4),
            "avg_pnl": round(avg_pnl, 6),
            "avg_win": round(avg_win, 6),
            "avg_loss": round(avg_loss, 6),
            "expectancy": round(expectancy, 6),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_dd, 6),
            "calmar_ratio": round(calmar, 4),
            "consistency": round(consistency, 4),
            "composite_score": round(composite, 4),
        }

    async def calibrate_confidence(self, strategy_name: str | None = None) -> dict:
        query = select(SignalOutcome)
        if strategy_name:
            query = query.where(SignalOutcome.strategy_name == strategy_name)
        query = query.where(SignalOutcome.outcome_close.isnot(None))
        result = await self.db.execute(query)
        outcomes = list(result.scalars().all())

        if not outcomes:
            return {"strategy": strategy_name or "all", "buckets": [], "ece": None}

        buckets = defaultdict(lambda: {"count": 0, "wins": 0})
        for o in outcomes:
            conf = float(o.entry_confidence)
            bucket = round(conf * 10) / 10
            bucket_key = f"{bucket:.1f}-{bucket + 0.1:.1f}"
            buckets[bucket_key]["count"] += 1
            if o.outcome_close == "WIN":
                buckets[bucket_key]["wins"] += 1

        bucket_data = []
        total_ece = 0.0
        total_samples = 0
        for bucket_key in sorted(buckets.keys()):
            b = buckets[bucket_key]
            win_rate = b["wins"] / b["count"] if b["count"] > 0 else 0
            low = float(bucket_key.split("-")[0])
            high = float(bucket_key.split("-")[1])
            mid_conf = (low + high) / 2
            gap = abs(mid_conf - win_rate)
            total_ece += gap * b["count"]
            total_samples += b["count"]
            bucket_data.append({
                "bucket": bucket_key,
                "confidence_mid": round(mid_conf, 2),
                "count": b["count"],
                "wins": b["wins"],
                "actual_win_rate": round(win_rate, 4),
                "calibration_gap": round(gap, 4),
            })

        ece = round(total_ece / total_samples, 4) if total_samples > 0 else None
        return {
            "strategy": strategy_name or "all",
            "buckets": bucket_data,
            "ece": ece,
            "total_samples": total_samples,
        }
