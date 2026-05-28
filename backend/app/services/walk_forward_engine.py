from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade
from app.core.logging import logger


@dataclass
class WindowResult:
    window_label: str
    start: datetime
    end: datetime
    trade_count: int
    expectancy: float
    win_rate: float
    sharpe: float
    max_drawdown: float
    signal_frequency: float


@dataclass
class WalkForwardReport:
    strategy_name: str
    windows: list[WindowResult] = field(default_factory=list)
    expectancy_stability: float = 0.0
    win_rate_drift: float = 0.0
    sharpe_drift: float = 0.0
    drawdown_drift: float = 0.0
    signal_frequency_drift: float = 0.0
    overfit_persistence_score: float = 0.0
    stability_score: float = 0.0
    survival_classification: str = "FAIL"  # "PASS" | "WEAK" | "FAIL"


class WalkForwardEngine:
    TRAIN_DAYS = 7
    VALIDATE_DAYS = 3
    TEST_DAYS = 3

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(self, strategy_name: str, max_windows: int = 6) -> WalkForwardReport:
        all_trades = await self._fetch_all_closed(strategy_name)
        if len(all_trades) < 20:
            return WalkForwardReport(
                strategy_name=strategy_name,
                survival_classification="FAIL",
                stability_score=0.0,
            )

        window_size_days = self.TRAIN_DAYS + self.VALIDATE_DAYS + self.TEST_DAYS
        windows = []
        total_days = 90

        for i in range(max_windows):
            offset = i * self.TEST_DAYS
            if offset + window_size_days > total_days:
                break

            end = datetime.now(timezone.utc) - timedelta(days=offset)
            test_end = end
            test_start = end - timedelta(days=self.TEST_DAYS)
            validate_end = test_start
            validate_start = validate_end - timedelta(days=self.VALIDATE_DAYS)
            train_end = validate_start
            train_start = train_end - timedelta(days=self.TRAIN_DAYS)

            train_trades = [t for t in all_trades if train_start <= (t.exit_timestamp or t.entry_timestamp) < train_end]
            validate_trades = [t for t in all_trades if validate_start <= (t.exit_timestamp or t.entry_timestamp) < validate_end]
            test_trades = [t for t in all_trades if test_start <= (t.exit_timestamp or t.entry_timestamp) < test_end]

            if len(test_trades) < 3:
                continue

            train_metrics = self._compute_window_metrics(train_trades)
            validate_metrics = self._compute_window_metrics(validate_trades)
            test_metrics = self._compute_window_metrics(test_trades)

            windows.append(WindowResult(
                window_label=f"W{i+1}_train{train_start.strftime('%m%d')}-test{test_end.strftime('%m%d')}",
                start=train_start, end=test_end,
                trade_count=test_metrics["count"],
                expectancy=test_metrics["expectancy"],
                win_rate=test_metrics["win_rate"],
                sharpe=test_metrics["sharpe"],
                max_drawdown=test_metrics["max_drawdown"],
                signal_frequency=test_metrics["signal_frequency"],
            ))

        if len(windows) < 2:
            return WalkForwardReport(
                strategy_name=strategy_name,
                windows=windows,
                survival_classification="FAIL",
                stability_score=0.0,
            )

        expectancies = [w.expectancy for w in windows]
        win_rates = [w.win_rate for w in windows]
        sharpes = [w.sharpe for w in windows]
        drawdowns = [w.max_drawdown for w in windows]
        frequencies = [w.signal_frequency for w in windows]

        exp_mean = sum(expectancies) / len(expectancies)
        exp_std = self._std(expectancies)
        wr_mean = sum(win_rates) / len(win_rates)
        wr_std = self._std(win_rates)
        sh_mean = sum(sharpes) / len(sharpes)
        sh_std = self._std(sharpes)
        dd_mean = sum(drawdowns) / len(drawdowns)
        dd_std = self._std(drawdowns)
        freq_mean = sum(frequencies) / len(frequencies)
        freq_std = self._std(frequencies)

        expectancy_stability = 1.0 - min(1.0, exp_std / (abs(exp_mean) + 0.001))
        win_rate_drift = wr_std / (wr_mean + 0.001)
        sharpe_drift = sh_std / (abs(sh_mean) + 0.001)
        drawdown_drift = dd_std / (dd_mean + 0.001)
        signal_frequency_drift = freq_std / (freq_mean + 0.001)

        positive_windows = sum(1 for e in expectancies if e > 0)
        positive_ratio = positive_windows / len(expectancies)
        overfit_persistence_score = 1.0 - positive_ratio

        stability_score = max(0, expectancy_stability * 0.4 + (1.0 - sharpe_drift) * 0.3 + (1.0 - drawdown_drift) * 0.3)

        if positive_ratio >= 0.66 and expectancy_stability > 0.3 and sharpe_drift < 1.0:
            classification = "PASS"
        elif positive_ratio >= 0.33 and expectancy_stability > 0:
            classification = "WEAK"
        else:
            classification = "FAIL"

        return WalkForwardReport(
            strategy_name=strategy_name,
            windows=windows,
            expectancy_stability=round(expectancy_stability, 4),
            win_rate_drift=round(win_rate_drift, 4),
            sharpe_drift=round(sharpe_drift, 4),
            drawdown_drift=round(drawdown_drift, 4),
            signal_frequency_drift=round(signal_frequency_drift, 4),
            overfit_persistence_score=round(overfit_persistence_score, 4),
            stability_score=round(stability_score, 4),
            survival_classification=classification,
        )

    def _compute_window_metrics(self, trades: list[Trade]) -> dict[str, Any]:
        if not trades:
            return {"count": 0, "expectancy": 0.0, "win_rate": 0.0, "sharpe": 0.0,
                    "max_drawdown": 0.0, "signal_frequency": 0.0}

        pnls = [float(t.pnl or 0) for t in trades]
        count = len(pnls)
        expectancy = sum(pnls) / count if count else 0
        win_rate = sum(1 for p in pnls if p > 0) / count if count else 0

        mean = sum(pnls) / count
        variance = sum((p - mean) ** 2 for p in pnls) / count if count > 1 else 0
        std = variance ** 0.5
        sharpe = mean / std if std > 0 else 0

        cumulative = 0
        peak = 0
        max_dd = 0
        for p in pnls:
            cumulative += p
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / max(peak, 0.001)
            max_dd = max(max_dd, dd)

        window_days = max((trades[-1].exit_timestamp - trades[0].exit_timestamp).total_seconds() / 86400, 1) if len(trades) > 1 and trades[-1].exit_timestamp and trades[0].exit_timestamp else 1
        signal_frequency = count / window_days

        return {"count": count, "expectancy": expectancy, "win_rate": win_rate,
                "sharpe": sharpe, "max_drawdown": max_dd, "signal_frequency": signal_frequency}

    def _std(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return variance ** 0.5

    async def _fetch_all_closed(self, strategy_name: str) -> list[Trade]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=180)
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
