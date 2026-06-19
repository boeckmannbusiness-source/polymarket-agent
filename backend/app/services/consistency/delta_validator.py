from app.domain.execution import ExecutionResult
from app.domain.portfolio import PortfolioSnapshot, ExecutionFeedback
from app.services.consistency.consistency_report import ConsistencyCheck


class DeltaValidator:
    def validate(self, result: ExecutionResult, portfolio: PortfolioSnapshot | None, feedback: ExecutionFeedback | None) -> list[ConsistencyCheck]:
        checks: list[ConsistencyCheck] = []

        checks.append(self._check_slippage_delta(result))
        checks.append(self._check_exposure_delta(result, portfolio))
        checks.append(self._check_latency_consistency(result))

        if feedback is not None and portfolio is not None:
            checks.append(self._check_portfolio_delta(feedback, portfolio))

        return checks

    @staticmethod
    def _check_slippage_delta(result: ExecutionResult) -> ConsistencyCheck:
        slippage_bps = result.simulated_slippage
        if slippage_bps is None:
            return ConsistencyCheck(name="slippage_delta_check", passed=False, expected="slippage_bps", actual="None")
        slippage_value = slippage_bps * 10000
        return ConsistencyCheck(
            name="slippage_delta_check",
            passed=0 <= slippage_value <= 10000,
            expected=str(slippage_value),
            actual=str(slippage_value),
        )

    @staticmethod
    def _check_exposure_delta(result: ExecutionResult, portfolio: PortfolioSnapshot | None) -> ConsistencyCheck:
        if portfolio is None or not result.fills:
            return ConsistencyCheck(name="exposure_delta_check", passed=True, expected="N/A", actual="no portfolio")
        total_fill_value = sum(f.size * f.price for f in result.fills)
        return ConsistencyCheck(
            name="exposure_delta_check",
            passed=True,
            expected=str(portfolio.exposure),
            actual=str(total_fill_value),
        )

    @staticmethod
    def _check_latency_consistency(result: ExecutionResult) -> ConsistencyCheck:
        if result.latency_ms is None:
            return ConsistencyCheck(name="latency_consistency_check", passed=False, expected="latency_ms", actual="None")
        return ConsistencyCheck(
            name="latency_consistency_check",
            passed=result.latency_ms >= 0,
            expected=">= 0",
            actual=str(result.latency_ms),
        )

    @staticmethod
    def _check_portfolio_delta(feedback: ExecutionFeedback, portfolio: PortfolioSnapshot) -> ConsistencyCheck:
        return ConsistencyCheck(
            name="portfolio_delta_check",
            passed=True,
            expected=str(portfolio.realized_pnl),
            actual=str(feedback.portfolio_delta),
        )
