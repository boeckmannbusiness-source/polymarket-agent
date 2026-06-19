from app.domain.execution import ExecutionResult
from app.domain.portfolio import PortfolioSnapshot, ExecutionFeedback
from app.services.shadow.portfolio_projector import PortfolioProjector


class ExecutionFeedbackService:
    def __init__(self, projector: PortfolioProjector | None = None):
        self._projector = projector or PortfolioProjector()

    def create(self, result: ExecutionResult, portfolio: PortfolioSnapshot | None = None) -> ExecutionFeedback:
        projections = self._projector.project(result, portfolio)
        portfolio_delta = 0.0
        if portfolio:
            total_before = float(portfolio.cash_balance + portfolio.exposure)
            total_after = float(
                (portfolio.cash_balance - (result.fees or portfolio.cash_balance))
                + sum(
                    float(p.estimated_pnl) for p in projections
                )
            )
            portfolio_delta = total_after - total_before

        slippage_realized = float(result.simulated_slippage or 0) * 10000
        fee_realized = float(result.fees or 0)
        latency_ms = result.latency_ms or 0.0

        route_efficiency = self._compute_route_efficiency(result)

        signal_id = None
        if result.metadata:
            signal_id = result.metadata.get("signal_id") or result.metadata.get("trade_id")

        return ExecutionFeedback(
            execution_id=result.execution_id,
            signal_id=signal_id,
            result_status=result.status,
            portfolio_delta=portfolio_delta,
            slippage_realized=slippage_realized,
            fee_realized=fee_realized,
            route_efficiency=route_efficiency,
            latency_ms=latency_ms,
            metadata={
                "instruction_count": len(result.instruction_trace) if result.instruction_trace else 0,
                "adapter": result.adapter,
            },
        )

    @staticmethod
    def _compute_route_efficiency(result: ExecutionResult) -> float:
        if not result.execution_path:
            return 1.0
        hops = len(result.execution_path)
        if hops <= 1:
            return 1.0
        penalty = 0.1 * (hops - 1)
        return max(0.0, 1.0 - penalty)
