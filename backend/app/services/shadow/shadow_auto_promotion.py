from app.core.logging import logger
from app.schemas.tournament import PromotionRecommendation
from app.services.shadow.strategy_tournament_service import tournament_service
from app.services.shadow.shadow_promotion_service import promotion_service


class ShadowAutoPromotionService:
    async def get_recommendations(self) -> list[PromotionRecommendation]:
        rankings = await tournament_service.get_rankings()
        recommendations: list[PromotionRecommendation] = []

        for r in rankings:
            window = await tournament_service.get_window_metrics(r.strategy)
            promotion = await promotion_service.evaluate_strategy(r.strategy)

            scores = {
                "7d": window.sharpe_7d,
                "30d": window.sharpe_30d,
                "lifetime": window.sharpe_lifetime,
            }
            active_window = max(scores, key=lambda k: abs(scores[k]))

            if promotion.recommended_tier == "LIVE" and r.confidence >= 80:
                recommendations.append(
                    PromotionRecommendation(
                        strategy=r.strategy,
                        action="promote",
                        from_tier="PAPER",
                        to_tier="LIVE",
                        window=active_window,
                        reason=f"Strong performance: Sharpe {r.sharpe:.2f}, confidence {r.confidence:.0f}",
                        score_7d=round(window.sharpe_7d, 4),
                        score_30d=round(window.sharpe_30d, 4),
                        score_lifetime=round(window.sharpe_lifetime, 4),
                    )
                )
            elif promotion.recommended_tier == "PAPER" and r.confidence >= 50:
                recommendations.append(
                    PromotionRecommendation(
                        strategy=r.strategy,
                        action="promote",
                        from_tier="SHADOW",
                        to_tier="PAPER",
                        window=active_window,
                        reason=f"Moderate performance: Sharpe {r.sharpe:.2f}, {r.total_trades} trades",
                        score_7d=round(window.sharpe_7d, 4),
                        score_30d=round(window.sharpe_30d, 4),
                        score_lifetime=round(window.sharpe_lifetime, 4),
                    )
                )
            elif r.confidence < 30 and r.total_trades > 10:
                recommendations.append(
                    PromotionRecommendation(
                        strategy=r.strategy,
                        action="hold",
                        from_tier="SHADOW",
                        to_tier="SHADOW",
                        window=active_window,
                        reason=f"Below threshold: Sharpe {r.sharpe:.2f}, confidence {r.confidence:.0f}",
                        score_7d=round(window.sharpe_7d, 4),
                        score_30d=round(window.sharpe_30d, 4),
                        score_lifetime=round(window.sharpe_lifetime, 4),
                    )
                )

        return recommendations


auto_promotion_service = ShadowAutoPromotionService()
