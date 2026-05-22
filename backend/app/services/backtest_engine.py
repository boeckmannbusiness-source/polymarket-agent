import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backtest import BacktestRun, BacktestTrade
from app.replay.engine import ReplayEngine, ReplayMode, ReplayedSignal
from app.services.execution_simulator import ExecutionSimulator


class BacktestEngine:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.replay_engine = ReplayEngine(db, ExecutionSimulator())

    async def execute(self, run: BacktestRun) -> BacktestRun:
        try:
            return await self._run(run)
        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)
            return run

    async def _run(self, run: BacktestRun) -> BacktestRun:
        cfg = run.strategy_config or {}
        strategy_names: list[str] = cfg.get("strategies", [cfg.get("strategy", "whale_following")])
        if isinstance(strategy_names, str):
            strategy_names = [strategy_names]

        mode_str = cfg.get("mode", "signal_only")
        try:
            mode = ReplayMode(mode_str)
        except ValueError:
            mode = ReplayMode.SIGNAL_ONLY

        strategy_cfg = cfg.get("config")
        initial_capital = float(run.initial_capital or 10000.0)

        run.status = "running"

        results = await self.replay_engine.run_multi(
            strategy_names=strategy_names,
            start_time=run.start_date,
            end_time=run.end_date,
            mode=mode,
            config=strategy_cfg,
        )

        all_trades: list[BacktestTrade] = []
        all_pnls: list[float] = []
        trade_timestamps: list[datetime] = []
        equity_values: list[float] = [initial_capital]
        equity_timestamps: list[datetime] = []

        for strategy_name, result in results.items():
            for signal in result.signals:
                pnl = signal.pnl_close or 0.0
                size = float(signal.execution_fill_size or 1.0)
                position_size = 1.0
                trade_pnl = pnl * position_size

                trade = BacktestTrade(
                    backtest_run_id=run.id,
                    market_id=None,
                    side="buy" if signal.signal.signal in ("BUY_YES",) else "sell",
                    outcome=signal.signal.signal,
                    entry_price=signal.execution_fill_price or signal.entry_price,
                    exit_price=signal.probability_close or signal.entry_price,
                    size=position_size,
                    pnl=trade_pnl,
                    entry_timestamp=signal.entry_timestamp,
                    exit_timestamp=None,
                    signal_type=signal.strategy_name,
                    extra_data={
                        "confidence": signal.signal.confidence,
                        "reason": signal.signal.reason,
                        "regime": signal.regime,
                        "outcome_close": signal.outcome_close,
                        "slippage": signal.execution_slippage,
                        "partial": signal.execution_partial,
                        "spread_cost": signal.execution_spread_cost,
                    },
                )
                all_trades.append(trade)
                all_pnls.append(trade_pnl)
                trade_timestamps.append(signal.entry_timestamp)

                if equity_timestamps:
                    equity_values.append(equity_values[-1] + trade_pnl)
                else:
                    equity_values.append(initial_capital + trade_pnl)
                equity_timestamps.append(signal.entry_timestamp)

        total_pnl = sum(all_pnls)
        final_capital = initial_capital + total_pnl
        metrics = self._compute_metrics(all_pnls, equity_values, initial_capital)

        run.total_pnl = total_pnl
        run.final_capital = final_capital
        run.total_trades = len(all_trades)
        run.win_rate = metrics["win_rate"]
        run.sharpe_ratio = metrics["sharpe_ratio"]
        run.sortino_ratio = metrics["sortino_ratio"]
        run.calmar_ratio = metrics["calmar_ratio"]
        run.max_drawdown = metrics["max_drawdown"]
        run.expectancy = metrics["expectancy"]
        run.profit_factor = metrics["profit_factor"]
        run.mode = mode_str
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)

        for t in all_trades:
            self.db.add(t)

        return run

    def _compute_metrics(
        self, pnls: list[float], equity: list[float], initial_capital: float
    ) -> dict[str, float]:
        total = len(pnls)
        if total == 0:
            return {
                "win_rate": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "max_drawdown": 0.0,
                "expectancy": 0.0,
                "profit_factor": 0.0,
            }

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        win_rate = len(wins) / total if total > 0 else 0.0

        expectancy = sum(pnls) / total if total > 0 else 0.0

        profit_factor = (
            sum(wins) / abs(sum(losses))
            if losses and abs(sum(losses)) > 1e-12
            else float("inf") if wins
            else 0.0
        )
        if profit_factor == float("inf"):
            profit_factor = 999.0

        max_drawdown = self._compute_max_drawdown(equity)

        annual_factor = math.sqrt(252)
        returns = []
        for i in range(1, len(equity)):
            prev = equity[i - 1]
            if prev != 0:
                returns.append((equity[i] - prev) / prev)

        if len(returns) < 2:
            return {
                "win_rate": round(win_rate, 6),
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "max_drawdown": round(max_drawdown, 6),
                "expectancy": round(expectancy, 6),
                "profit_factor": round(profit_factor, 6),
            }

        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance) if variance > 0 else 1e-12

        downside = [r for r in returns if r < 0]
        downside_variance = (
            sum(r ** 2 for r in downside) / len(returns) if downside else 1e-12
        )
        downside_std = math.sqrt(downside_variance) if downside_variance > 0 else 1e-12

        sharpe = (mean_ret / std_dev) * annual_factor if std_dev > 1e-12 else 0.0
        sortino = (mean_ret / downside_std) * annual_factor if downside_std > 1e-12 else 0.0

        calmar = (
            mean_ret * len(returns) / max_drawdown
            if max_drawdown > 1e-12
            else 0.0
        )

        return {
            "win_rate": round(win_rate, 6),
            "sharpe_ratio": round(sharpe, 6),
            "sortino_ratio": round(sortino, 6),
            "calmar_ratio": round(calmar, 6),
            "max_drawdown": round(max_drawdown, 6),
            "expectancy": round(expectancy, 6),
            "profit_factor": round(profit_factor, 6),
        }

    @staticmethod
    def _compute_max_drawdown(equity: list[float]) -> float:
        if len(equity) < 2:
            return 0.0
        peak = equity[0]
        max_dd = 0.0
        for val in equity:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd
