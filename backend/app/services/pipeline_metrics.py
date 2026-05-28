import time
from datetime import datetime, timezone
from asyncio import Lock

_signal_count = 0
_risk_rejected_count = 0
_execution_success_count = 0
_execution_failure_count = 0
_total_slippage = 0.0
_total_executions = 0
_crash_count = 0
_exit_count = 0
_forced_exit_count = 0
_strategy_kill_count = 0
_strategy_edge_score = 0.0
_overfit_risk_score = 0.0
_survival_probability_30d = 0.0
_capital_efficiency_rank = 0
_live_state = "SHADOW"
_live_consecutive_losses = 0
_live_daily_pnl = 0.0
_health_alerts_count = 0
_exposure_rejections_total = 0
_total_open_exposure = 0.0
_exposure_utilization_pct = 0.0
_duplicate_market_rejections_total = 0
_trading_halt_count = 0
_halt_reason = ""
_kill_switch_activations_total = 0
_start_time = time.time()
_lock = Lock()


async def inc_signal():
    global _signal_count
    async with _lock:
        _signal_count += 1


async def inc_risk_rejected():
    global _risk_rejected_count
    async with _lock:
        _risk_rejected_count += 1


async def inc_execution_success():
    global _execution_success_count
    async with _lock:
        _execution_success_count += 1


async def inc_execution_failure():
    global _execution_failure_count
    async with _lock:
        _execution_failure_count += 1


async def record_slippage(slippage: float):
    global _total_slippage, _total_executions
    async with _lock:
        _total_slippage += slippage
        _total_executions += 1


async def inc_crash():
    global _crash_count
    async with _lock:
        _crash_count += 1


async def inc_exit():
    global _exit_count
    async with _lock:
        _exit_count += 1


async def inc_forced_exit():
    global _forced_exit_count
    async with _lock:
        _forced_exit_count += 1


async def inc_strategy_kill():
    global _strategy_kill_count
    async with _lock:
        _strategy_kill_count += 1


async def set_phase45_metrics(edge_score: float, overfit_score: float, survival_prob: float, efficiency_rank: int):
    global _strategy_edge_score, _overfit_risk_score, _survival_probability_30d, _capital_efficiency_rank
    async with _lock:
        _strategy_edge_score = edge_score
        _overfit_risk_score = overfit_score
        _survival_probability_30d = survival_prob
        _capital_efficiency_rank = efficiency_rank


async def set_phase5_metrics(state: str, consecutive_losses: int, daily_pnl: float, alerts_count: int):
    global _live_state, _live_consecutive_losses, _live_daily_pnl, _health_alerts_count
    async with _lock:
        _live_state = state
        _live_consecutive_losses = consecutive_losses
        _live_daily_pnl = daily_pnl
        _health_alerts_count = alerts_count


async def inc_exposure_rejection():
    global _exposure_rejections_total
    async with _lock:
        _exposure_rejections_total += 1


async def set_exposure_metrics(total_exposure: float, utilization_pct: float):
    global _total_open_exposure, _exposure_utilization_pct
    async with _lock:
        _total_open_exposure = total_exposure
        _exposure_utilization_pct = utilization_pct


async def inc_duplicate_market_rejection():
    global _duplicate_market_rejections_total
    async with _lock:
        _duplicate_market_rejections_total += 1


async def inc_trading_halt(reason: str):
    global _trading_halt_count, _halt_reason
    async with _lock:
        _trading_halt_count += 1
        _halt_reason = reason


async def inc_kill_switch_activation():
    global _kill_switch_activations_total
    async with _lock:
        _kill_switch_activations_total += 1


async def get_metrics() -> dict:
    global _signal_count, _risk_rejected_count, _execution_success_count
    global _execution_failure_count, _total_slippage, _total_executions
    global _crash_count, _exit_count, _forced_exit_count, _strategy_kill_count
    global _strategy_edge_score, _overfit_risk_score, _survival_probability_30d, _capital_efficiency_rank
    global _live_state, _live_consecutive_losses, _live_daily_pnl, _health_alerts_count
    global _exposure_rejections_total, _total_open_exposure, _exposure_utilization_pct
    global _duplicate_market_rejections_total, _trading_halt_count, _halt_reason
    global _kill_switch_activations_total, _start_time
    async with _lock:
        elapsed = time.time() - _start_time
        elapsed_min = max(elapsed / 60, 1)
        signal_rate = _signal_count / elapsed_min
        total_exec = _execution_success_count + _execution_failure_count
        exec_success_rate = _execution_success_count / total_exec if total_exec > 0 else 1.0
        total_risk = _signal_count + _risk_rejected_count
        risk_rejection_rate = _risk_rejected_count / total_risk if total_risk > 0 else 0.0
        avg_slip = _total_slippage / _total_executions if _total_executions > 0 else 0.0

        return {
            "signal_rate_per_minute": round(signal_rate, 2),
            "risk_rejection_rate": round(risk_rejection_rate, 4),
            "execution_success_rate": round(exec_success_rate, 4),
            "avg_slippage": round(avg_slip, 6),
            "crash_count": _crash_count,
            "signals_total": _signal_count,
            "risk_rejected_total": _risk_rejected_count,
            "executions_success": _execution_success_count,
            "executions_failed": _execution_failure_count,
            "exits_total": _exit_count,
            "forced_exit_rate": round(_forced_exit_count / max(_exit_count, 1), 4),
            "strategy_kill_count": _strategy_kill_count,
            "strategy_edge_score": round(_strategy_edge_score, 4),
            "overfit_risk_score": round(_overfit_risk_score, 4),
            "survival_probability_30d": round(_survival_probability_30d, 4),
            "capital_efficiency_rank": _capital_efficiency_rank,
            "live_state": _live_state,
            "live_consecutive_losses": _live_consecutive_losses,
            "live_daily_pnl": round(_live_daily_pnl, 4),
            "health_alerts_count": _health_alerts_count,
            "exposure_rejections_total": _exposure_rejections_total,
            "total_open_exposure": round(_total_open_exposure, 2),
            "exposure_utilization_pct": round(_exposure_utilization_pct, 1),
            "duplicate_market_rejections_total": _duplicate_market_rejections_total,
            "trading_halt_count": _trading_halt_count,
            "halt_reason": _halt_reason,
            "kill_switch_activations_total": _kill_switch_activations_total,
            "uptime_seconds": round(elapsed, 1),
        }
