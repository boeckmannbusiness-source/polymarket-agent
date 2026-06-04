from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.schemas.research import ResearchReport, PortfolioReport
from app.services.shadow.shadow_execution_service import shadow_execution_service
from app.services.shadow.shadow_analytics_service import analytics_service
from app.services.shadow.shadow_benchmark_service import benchmark_service
from app.services.shadow.shadow_promotion_service import promotion_service
from app.services.research.strategy_health_service import health_service
from app.services.shadow.strategy_tournament_service import tournament_service

REPORT_CACHE_PREFIX = "research:report:cache:"
REPORT_CACHE_TTL = 300


class ResearchReportService:
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
            data = await r.get(f"{REPORT_CACHE_PREFIX}{key}")
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
            await r.setex(f"{REPORT_CACHE_PREFIX}{key}", REPORT_CACHE_TTL, json.dumps(data, default=str))
        except Exception:
            pass

    async def generate_strategy_report(self, strategy: str) -> ResearchReport:
        cache_key = f"strategy:{strategy}"
        cached = await self._get_cached(cache_key)
        if cached:
            return ResearchReport(**cached)

        analytics = await analytics_service.get_strategy_analytics(strategy)
        benchmark = await benchmark_service.get_strategy_benchmark(strategy)
        promotion = await promotion_service.evaluate_strategy(strategy)
        health = await health_service.compute_health(strategy)

        strengths: list[str] = []
        weaknesses: list[str] = []
        risk_factors: list[str] = []

        if analytics.sharpe_ratio >= 1.0:
            strengths.append(f"Strong Sharpe ratio ({analytics.sharpe_ratio:.2f})")
        elif analytics.sharpe_ratio < 0:
            weaknesses.append(f"Negative Sharpe ratio ({analytics.sharpe_ratio:.2f})")
            risk_factors.append("Negative risk-adjusted returns")

        if analytics.sortino_ratio >= 1.0:
            strengths.append(f"Strong downside protection (Sortino {analytics.sortino_ratio:.2f})")

        if analytics.win_rate >= 0.55:
            strengths.append(f"High win rate ({analytics.win_rate:.1%})")
        elif analytics.win_rate < 0.4:
            weaknesses.append(f"Low win rate ({analytics.win_rate:.1%})")
            risk_factors.append("Below-average win rate threatens consistency")

        if analytics.profit_factor >= 2.0:
            strengths.append(f"Excellent profit factor ({analytics.profit_factor:.2f})")
        elif analytics.profit_factor < 1.0:
            weaknesses.append(f"Profit factor below 1.0 ({analytics.profit_factor:.2f})")
            risk_factors.append("Strategy loses more than it gains")

        if analytics.max_drawdown <= 0.1:
            strengths.append(f"Low max drawdown ({analytics.max_drawdown:.1%})")
        elif analytics.max_drawdown > 0.25:
            weaknesses.append(f"High max drawdown ({analytics.max_drawdown:.1%})")
            risk_factors.append("Elevated drawdown risk")

        if benchmark.alpha > 0:
            strengths.append(f"Positive alpha vs benchmark ({benchmark.alpha:.4f})")
        else:
            weaknesses.append(f"Negative alpha ({benchmark.alpha:.4f})")
            risk_factors.append("Strategy underperforms benchmark")

        if health.level == "CRITICAL":
            weaknesses.append("Health status is CRITICAL")
            risk_factors.append("Strategy health requires immediate attention")
        elif health.level == "WARNING":
            weaknesses.append("Health status is WARNING")
            risk_factors.append("Monitoring recommended — health declining")

        if promotion.confidence_score >= 80:
            strengths.append(f"High promotion confidence ({promotion.confidence_score:.0f})")
        elif promotion.confidence_score < 40:
            weaknesses.append(f"Low promotion confidence ({promotion.confidence_score:.0f})")
            risk_factors.append("Insufficient confidence for promotion")

        performance_summary = {
            "total_pnl": analytics.total_pnl,
            "realized_pnl": analytics.realized_pnl,
            "win_rate": analytics.win_rate,
            "sharpe_ratio": analytics.sharpe_ratio,
            "sortino_ratio": analytics.sortino_ratio,
            "max_drawdown": analytics.max_drawdown,
            "profit_factor": analytics.profit_factor,
            "expectancy": analytics.expectancy,
            "total_trades": analytics.total_signals,
        }

        result = ResearchReport(
            strategy=strategy,
            generated_at=datetime.now(timezone.utc).isoformat(),
            performance_summary=performance_summary,
            strengths=strengths,
            weaknesses=weaknesses,
            benchmark_comparison=benchmark.model_dump(),
            promotion_recommendation=promotion.model_dump(),
            risk_factors=risk_factors,
        )
        await self._set_cache(cache_key, result.model_dump())
        return result

    async def generate_portfolio_report(self) -> PortfolioReport:
        cache_key = "portfolio"
        cached = await self._get_cached(cache_key)
        if cached:
            return PortfolioReport(**cached)

        await shadow_execution_service._ensure_redis()
        strategies = sorted(set(e.strategy for e in shadow_execution_service.get_all_executions()))

        top_performers: list[dict[str, Any]] = []
        worst_performers: list[dict[str, Any]] = []
        concentration_risks: list[dict[str, Any]] = []
        promotion_opportunities: list[dict[str, Any]] = []
        retirement_candidates: list[dict[str, Any]] = []

        all_analytics = []
        for s in strategies:
            a = await analytics_service.get_strategy_analytics(s)
            p = await promotion_service.evaluate_strategy(s)
            h = await health_service.compute_health(s)
            all_analytics.append((s, a, p, h))

        all_analytics.sort(key=lambda x: x[1].total_pnl, reverse=True)
        for s, a, p, h in all_analytics[:5]:
            top_performers.append({"strategy": s, "total_pnl": a.total_pnl, "sharpe": a.sharpe_ratio, "win_rate": a.win_rate})

        for s, a, p, h in all_analytics[-5:]:
            worst_performers.append({"strategy": s, "total_pnl": a.total_pnl, "sharpe": a.sharpe_ratio, "health_score": h.score})

        total_pnl = sum(a.total_pnl for _, a, _, _ in all_analytics)
        for s, a, _, _ in all_analytics:
            if total_pnl != 0:
                exposure = abs(a.total_pnl / total_pnl)
                if exposure > 0.3:
                    concentration_risks.append({"strategy": s, "exposure_pct": round(exposure * 100, 1), "total_pnl": a.total_pnl})

        for s, _, p, _ in all_analytics:
            if p.recommended_tier == "LIVE" and p.confidence_score >= 80:
                promotion_opportunities.append({"strategy": s, "recommended_tier": p.recommended_tier, "confidence": p.confidence_score})

        for s, a, p, h in all_analytics:
            is_retirement = False
            reasons: list[str] = []
            if p.confidence_score < 30:
                is_retirement = True
                reasons.append("Low confidence")
            if h.level == "CRITICAL":
                is_retirement = True
                reasons.append("Critical health")
            if a.total_pnl < 0 and a.sharpe_ratio < 0:
                is_retirement = True
                reasons.append("Negative PnL and Sharpe")
            if is_retirement:
                retirement_candidates.append({"strategy": s, "reasons": reasons, "confidence": p.confidence_score, "health": h.level})

        result = PortfolioReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_strategies=len(strategies),
            top_performers=top_performers,
            worst_performers=worst_performers,
            concentration_risks=concentration_risks,
            promotion_opportunities=promotion_opportunities,
            retirement_candidates=retirement_candidates,
        )
        await self._set_cache(cache_key, result.model_dump())
        return result

    async def invalidate_cache(self):
        r = await self._safe_redis()
        if not r:
            return
        try:
            keys = await r.keys(f"{REPORT_CACHE_PREFIX}*")
            if keys:
                await r.delete(*keys)
        except Exception:
            pass


report_service = ResearchReportService()
