from fastapi import APIRouter, HTTPException
from app.services.optimization.autonomous_optimization_pipeline import autonomous_optimization_pipeline
from app.services.optimization.portfolio_optimization_engine import portfolio_optimization_engine
from app.services.optimization.regime_expected_return_model import regime_expected_return_model
from app.services.optimization.risk_model_service import risk_model_service
from app.services.optimization.monte_carlo_simulation_service import monte_carlo_simulation_service
from app.services.optimization.allocation_learning_service import allocation_learning_service
from app.schemas.optimization import (
    PortfolioOptimizationReport,
    MonteCarloPortfolioReport,
    RiskModelOutput,
    RegimeExpectedReturnsOutput,
)
from app.core.metrics import (
    portfolio_optimization_runs,
    monte_carlo_simulations_executed,
    risk_model_updates,
)

router = APIRouter()


@router.get("/portfolio", response_model=PortfolioOptimizationReport | dict)
async def get_portfolio_optimization():
    report = await autonomous_optimization_pipeline.get_latest()
    if report is None:
        return {"status": "no_data", "message": "No optimization report available yet"}
    return report


@router.get("/simulation", response_model=MonteCarloPortfolioReport | dict)
async def get_monte_carlo_simulation():
    report = await monte_carlo_simulation_service.get_latest()
    if report is None:
        return {"status": "no_data", "message": "No simulation data available yet"}
    return report


@router.get("/risk", response_model=RiskModelOutput | dict)
async def get_risk_model():
    output = await risk_model_service.get_latest()
    if output is None:
        return {"status": "no_data", "message": "No risk model data available yet"}
    return output


@router.get("/expected-returns", response_model=RegimeExpectedReturnsOutput | dict)
async def get_expected_returns():
    output = await regime_expected_return_model.get_latest()
    if output is None:
        return {"status": "no_data", "message": "No expected returns data available yet"}
    return output


@router.post("/run")
async def trigger_optimization_run():
    try:
        from app.services.control.control_plane import control_plane
        state = await control_plane.get_state()
        if not state.get("trading_enabled", True):
            return {
                "job_id": None,
                "status": "skipped",
                "message": "Optimization skipped: trading disabled",
            }
    except Exception:
        pass

    portfolio_optimization_runs.inc()

    report = await autonomous_optimization_pipeline.run(
        strategy_ids=None,
        expected_returns_map=None,
        regime_probabilities=None,
        strategy_performance_by_regime=None,
        base_correlations=None,
        tier_caps=None,
        current_weights=None,
        actual_returns=None,
        regime_accuracy=None,
        stress_survivability=None,
        regime="low_volatility",
        seed=42,
    )

    if report.monte_carlo:
        monte_carlo_simulations_executed.inc()
    if report.risk_model:
        risk_model_updates.inc()

    return {
        "job_id": report.report_id,
        "status": "completed",
        "summary": report.summary,
    }
