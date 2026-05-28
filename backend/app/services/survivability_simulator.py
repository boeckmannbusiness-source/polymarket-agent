import random
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade, MarketEvent
from app.core.logging import logger


@dataclass
class SurvivalReport:
    expected_drawdown: float
    probability_of_ruin: float
    expected_return: float
    volatility_stability: float
    survived_simulations: int = 0
    total_simulations: int = 0
    return_distribution: list[float] = field(default_factory=list)
    drawdown_curve: list[float] = field(default_factory=list)


class SurvivabilitySimulator:
    REGIMES = ["crisis", "normal", "extreme", "high_volatility", "low_volatility"]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def simulate(
        self,
        strategy_name: str,
        days: int = 30,
        simulations: int = 1000,
    ) -> SurvivalReport:
        trades = await self._fetch_historical_trades(strategy_name, days=min(days, 90))
        if len(trades) < 5:
            return SurvivalReport(
                expected_drawdown=0.0, probability_of_ruin=1.0,
                expected_return=0.0, volatility_stability=0.0,
                total_simulations=simulations,
            )

        pnls = [float(t.pnl or 0) for t in trades]
        slippages = [float(t.slippage or 0.001) for t in trades if t.slippage]
        mean_pnl = sum(pnls) / len(pnls) if pnls else 0
        std_pnl = self._std(pnls) if len(pnls) > 1 else abs(mean_pnl)
        avg_slippage = sum(slippages) / len(slippages) if slippages else 0.001

        regime_sequence = self._generate_regime_sequence(days)
        capital = 10000.0
        initial_capital = capital
        all_final_returns = []
        all_drawdowns = []
        survival_count = 0

        for sim in range(simulations):
            sim_capital = float(initial_capital)
            peak = float(initial_capital)
            sim_drawdowns = []
            trade_count = max(1, int(len(trades) * (days / 30)))

            for i in range(trade_count):
                regime = regime_sequence[i % len(regime_sequence)]
                regime_shock = self._regime_shock(regime)

                slippage_shock = avg_slippage * random.uniform(1.0, 3.0)
                if regime in ("crisis", "high_volatility", "extreme"):
                    slippage_shock *= random.uniform(1.5, 3.0)

                execution_delay = random.uniform(0, 1)
                delay_penalty = 1.0 - execution_delay * 0.01

                raw_return = random.gauss(mean_pnl, std_pnl)
                stressed_return = raw_return * regime_shock * delay_penalty - (slippage_shock * 100)
                sim_capital += stressed_return

                if sim_capital > peak:
                    peak = sim_capital
                dd = (peak - sim_capital) / peak if peak > 0 else 0
                sim_drawdowns.append(dd)

                if sim_capital <= 0:
                    break

            max_dd = max(sim_drawdowns) if sim_drawdowns else 0
            final_return = (sim_capital - initial_capital) / initial_capital

            all_final_returns.append(final_return)
            all_drawdowns.append(max_dd)
            if sim_capital > 0:
                survival_count += 1

        expected_return = sum(all_final_returns) / len(all_final_returns)
        expected_drawdown = sum(all_drawdowns) / len(all_drawdowns)
        prob_ruin = 1.0 - (survival_count / simulations)

        sorted_dds = sorted(all_drawdowns)
        worst_dd_idx = max(1, int(len(sorted_dds) * 0.95))
        worst_dd = sorted_dds[-worst_dd_idx] if sorted_dds else 0

        return_dist_std = self._std(all_final_returns)
        volatility_stability = max(0, 1.0 - min(1.0, return_dist_std / (abs(expected_return) + 0.001)))

        return SurvivalReport(
            expected_drawdown=round(worst_dd, 6),
            probability_of_ruin=round(prob_ruin, 6),
            expected_return=round(expected_return, 6),
            volatility_stability=round(volatility_stability, 6),
            survived_simulations=survival_count,
            total_simulations=simulations,
            return_distribution=all_final_returns,
            drawdown_curve=sorted(all_drawdowns),
        )

    def _generate_regime_sequence(self, days: int) -> list[str]:
        sequence = []
        base_weights = {
            "crisis": 0.05, "normal": 0.40, "extreme": 0.10,
            "high_volatility": 0.25, "low_volatility": 0.20,
        }
        regimes = list(base_weights.keys())
        weights = list(base_weights.values())
        for _ in range(days * 4):
            seq_start = random.random()
            cumulative = 0
            for i, regime in enumerate(regimes):
                cumulative += weights[i]
                if seq_start <= cumulative:
                    sequence.append(regime)
                    break
        return sequence

    def _regime_shock(self, regime: str) -> float:
        shocks = {
            "crisis": random.uniform(-3.0, -0.5),
            "normal": random.uniform(0.5, 1.5),
            "extreme": random.uniform(-2.0, 2.0),
            "high_volatility": random.uniform(-1.5, 2.0),
            "low_volatility": random.uniform(0.8, 1.2),
        }
        return shocks.get(regime, 1.0)

    def _std(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return variance ** 0.5

    async def _fetch_historical_trades(self, strategy_name: str, days: int) -> list[Trade]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
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
