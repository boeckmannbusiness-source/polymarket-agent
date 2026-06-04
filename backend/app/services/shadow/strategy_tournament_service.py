import math
from typing import Any

from app.core.logging import logger
from app.schemas.tournament import TournamentRanking, TournamentWindowMetrics
from app.services.shadow.shadow_execution_service import (
    shadow_execution_service,
    ShadowExecution,
)
from app.services.shadow.shadow_analytics_service import analytics_service
from app.services.shadow.shadow_benchmark_service import benchmark_service
from app.services.shadow.shadow_promotion_service import promotion_service

TOURNAMENT_CACHE_PREFIX = "shadow:tournament:cache:"
TOURNAMENT_CACHE_TTL = 120


class StrategyTournamentService:
    async def _safe_redis(self):
        try:
            from app.redis import get_redis
            return await get_redis()
        except Exception:
            return None

    async def _get_cached(self, key: str) -> dict[str, Any] | None:
        r = await self._safe_redis()
        if not r:
            return None
        try:
            import json
            data = await r.get(f"{TOURNAMENT_CACHE_PREFIX}{key}")
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def _set_cache(self, key: str, data: dict[str, Any]):
        r = await self._safe_redis()
        if not r:
            return
        try:
            import json
            await r.setex(
                f"{TOURNAMENT_CACHE_PREFIX}{key}",
                TOURNAMENT_CACHE_TTL,
                json.dumps(data, default=str),
            )
        except Exception:
            pass

    def _compute_composite_score(
        self,
        sharpe: float,
        sortino: float,
        win_rate: float,
        expectancy: float,
        drawdown: float,
        alpha: float,
        trade_count: int,
    ) -> float:
        s_sharpe = max(min((sharpe + 2) / 4, 1.0), 0.0) * 20
        s_sortino = max(min((sortino + 2) / 4, 1.0), 0.0) * 15
        s_win = win_rate * 15
        s_exp = max(min(expectancy * 10, 1.0), 0.0) * 10
        s_dd = max(1.0 - drawdown, 0.0) * 15
        s_alpha = max(min((alpha + 5) / 10, 1.0), 0.0) * 15
        s_trades = min(trade_count / 50, 1.0) * 10
        return round(s_sharpe + s_sortino + s_win + s_exp + s_dd + s_alpha + s_trades, 4)

    async def get_window_metrics(self, strategy: str) -> TournamentWindowMetrics:
        await shadow_execution_service._ensure_redis()
        all_execs = shadow_execution_service.get_all_executions()
        strat_execs = [e for e in all_execs if e.strategy == strategy]

        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        cutoff_7d = now - timedelta(days=7)
        cutoff_30d = now - timedelta(days=30)

        def _pnl_in_window(execs: list[ShadowExecution], cutoff) -> list[float]:
            pnls = []
            for e in execs:
                if e.status == "closed" and e.realized_pnl is not None and e.entry_timestamp:
                    try:
                        ts = datetime.fromisoformat(e.entry_timestamp)
                        if ts >= cutoff:
                            pnls.append(e.realized_pnl)
                    except (ValueError, TypeError):
                        pass
            return pnls

        pnls_7d = _pnl_in_window(strat_execs, cutoff_7d)
        pnls_30d = _pnl_in_window(strat_execs, cutoff_30d)
        pnls_all = [e.realized_pnl for e in strat_execs if e.status == "closed" and e.realized_pnl is not None]

        def _win_rate(pnls: list[float]) -> float:
            return sum(1 for p in pnls if p > 0) / len(pnls) if pnls else 0.0

        def _sharpe(pnls: list[float]) -> float:
            n = len(pnls)
            if n < 2:
                return 0.0
            mean = sum(pnls) / n
            var = sum((p - mean) ** 2 for p in pnls) / (n - 1)
            std = math.sqrt(var) if var > 0 else 0.0001
            return (mean / std) * math.sqrt(252)

        return TournamentWindowMetrics(
            strategy=strategy,
            pnl_7d=round(sum(pnls_7d), 4),
            pnl_30d=round(sum(pnls_30d), 4),
            pnl_lifetime=round(sum(pnls_all), 4),
            trades_7d=len(pnls_7d),
            trades_30d=len(pnls_30d),
            trades_lifetime=len(pnls_all),
            win_rate_7d=round(_win_rate(pnls_7d), 4),
            win_rate_30d=round(_win_rate(pnls_30d), 4),
            win_rate_lifetime=round(_win_rate(pnls_all), 4),
            sharpe_7d=round(_sharpe(pnls_7d), 4),
            sharpe_30d=round(_sharpe(pnls_30d), 4),
            sharpe_lifetime=round(_sharpe(pnls_all), 4),
        )

    async def get_rankings(self) -> list[TournamentRanking]:
        cached = await self._get_cached("rankings")
        if cached:
            return [TournamentRanking(**r) for r in cached]

        await shadow_execution_service._ensure_redis()
        strategies = set(e.strategy for e in shadow_execution_service.get_all_executions())
        if not strategies:
            return []

        rankings: list[TournamentRanking] = []
        for s in sorted(strategies):
            analytics = await analytics_service.get_strategy_analytics(s)
            benchmark = await benchmark_service.get_strategy_benchmark(s)
            promotion = await promotion_service.evaluate_strategy(s)
            metrics = await self.get_window_metrics(s)

            score = self._compute_composite_score(
                sharpe=analytics.sharpe_ratio,
                sortino=analytics.sortino_ratio,
                win_rate=analytics.win_rate,
                expectancy=analytics.expectancy,
                drawdown=analytics.max_drawdown,
                alpha=benchmark.alpha,
                trade_count=analytics.closed_positions + analytics.executed_signals,
            )

            ranking = TournamentRanking(
                strategy=s,
                rank=0,
                score=score,
                percentile=0.0,
                confidence=promotion.confidence_score,
                tier=promotion.recommended_tier,
                trend="stable",
                sharpe=round(analytics.sharpe_ratio, 4),
                sortino=round(analytics.sortino_ratio, 4),
                win_rate=round(analytics.win_rate, 4),
                expectancy=round(analytics.expectancy, 6),
                max_drawdown=round(analytics.max_drawdown, 4),
                alpha=round(benchmark.alpha, 4),
                total_trades=analytics.closed_positions,
            )
            rankings.append(ranking)

        rankings.sort(key=lambda r: r.score, reverse=True)
        for i, r in enumerate(rankings):
            r.rank = i + 1
            r.percentile = round((len(rankings) - i) / len(rankings) * 100, 1)
            r.trend = self._determine_trend(r.strategy)

        await self._set_cache("rankings", [r.model_dump() for r in rankings])
        return rankings

    def _determine_trend(self, strategy: str) -> str:
        return "stable"

    async def invalidate_cache(self):
        r = await self._safe_redis()
        if not r:
            return
        try:
            keys = await r.keys(f"{TOURNAMENT_CACHE_PREFIX}*")
            if keys:
                await r.delete(*keys)
        except Exception:
            pass


tournament_service = StrategyTournamentService()
