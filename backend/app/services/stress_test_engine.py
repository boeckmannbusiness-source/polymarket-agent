from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any
import random

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade, MarketEvent
from app.models.portfolio import PortfolioSnapshot
from app.core.logging import logger


@dataclass
class StressTestResult:
    scenario: str
    portfolio_survived: bool
    forced_liquidations: int
    kill_switch_activated: bool
    kill_switch_delay_seconds: float
    max_drawdown: float
    final_capital: float
    survived_pct: float


class StressTestEngine:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._initial_capital = 10000.0

    async def run_all(self, simulations: int = 200) -> list[StressTestResult]:
        return [
            await self._simulate_ws_disconnect(simulations),
            await self._simulate_stale_feed(simulations),
            await self._simulate_liquidity_collapse(simulations),
            await self._simulate_correlated_crash(simulations),
            await self._simulate_slippage_spike(simulations),
            await self._simulate_delayed_execution(simulations),
            await self._simulate_spread_widening(simulations),
        ]

    async def _simulate_ws_disconnect(self, sims: int) -> StressTestResult:
        capital = self._initial_capital
        peak = capital
        liquidations = 0
        kill_switch = False
        kill_delay = 0.0
        survived = 0.0

        for i in range(sims):
            disconnect_minutes = random.randint(5, 60)
            trades = await self._fetch_recent_trades(7)
            sim_cap = float(capital)
            sim_peak = peak
            liq = 0

            for j, trade in enumerate(trades[:20]):
                if j * 2 > disconnect_minutes:
                    break
                pnl_impact = float(trade.pnl or 0) * random.uniform(-3.0, -1.5)
                sim_cap += pnl_impact
                if sim_cap > sim_peak:
                    sim_peak = sim_cap
                if sim_cap <= 0:
                    liq += 1
                    break

            if sim_cap <= capital * 0.5:
                kill_switch = True
                kill_delay = disconnect_minutes * 60 * random.uniform(1.0, 3.0)

            if sim_cap > 0:
                survived += 1

            capital = (capital * i + sim_cap) / (i + 1) if i > 0 else sim_cap
            liquidations += liq

        max_dd = (peak - capital) / peak if peak > 0 else 0
        return StressTestResult(
            scenario="ws_disconnect",
            portfolio_survived=survived / sims > 0.5,
            forced_liquidations=liquidations,
            kill_switch_activated=kill_switch,
            kill_switch_delay_seconds=kill_delay,
            max_drawdown=max_dd,
            final_capital=capital,
            survived_pct=survived / sims if sims > 0 else 0,
        )

    async def _simulate_stale_feed(self, sims: int) -> StressTestResult:
        capital = self._initial_capital
        peak = capital
        liquidations = 0
        kill_switch = False
        kill_delay = 60.0
        survived = 0.0

        for i in range(sims):
            stall_minutes = random.randint(15, 120)
            trades = await self._fetch_recent_trades(7)
            sim_cap = float(capital)
            liq = 0

            for j, trade in enumerate(trades[:30]):
                if j * 5 > stall_minutes:
                    break
                price_divergence = random.uniform(-0.3, 0.3)
                pnl_impact = float(trade.pnl or 0) * (1.0 + price_divergence) - abs(float(trade.pnl or 0)) * 0.5
                sim_cap += pnl_impact
                if sim_cap > peak:
                    peak = sim_cap
                if sim_cap <= 0:
                    liq += 1
                    break

            if sim_cap <= capital * 0.6:
                kill_switch = True

            if sim_cap > 0:
                survived += 1
            capital = (capital * i + sim_cap) / (i + 1) if i > 0 else sim_cap
            liquidations += liq

        max_dd = (peak - capital) / peak if peak > 0 else 0
        return StressTestResult(
            scenario="stale_feed",
            portfolio_survived=survived / sims > 0.5,
            forced_liquidations=liquidations,
            kill_switch_activated=kill_switch,
            kill_switch_delay_seconds=kill_delay,
            max_drawdown=max_dd,
            final_capital=capital,
            survived_pct=survived / sims if sims > 0 else 0,
        )

    async def _simulate_liquidity_collapse(self, sims: int) -> StressTestResult:
        capital = self._initial_capital
        peak = capital
        liquidations = 0
        kill_switch = False
        kill_delay = 120.0
        survived = 0.0

        for i in range(sims):
            trades = await self._fetch_recent_trades(7)
            sim_cap = float(capital)
            liq = 0
            for j, trade in enumerate(trades[:15]):
                liq_shock = random.uniform(0.3, 0.8)
                slippage_penalty = float(trade.filled_size or trade.size or 0) * random.uniform(0.05, 0.3)
                pnl_impact = -abs(float(trade.pnl or 0)) * liq_shock - slippage_penalty
                sim_cap += pnl_impact
                if sim_cap > peak:
                    peak = sim_cap
                if sim_cap <= 0:
                    liq += 1
                    break

            if sim_cap <= capital * 0.4:
                kill_switch = True
            if sim_cap > 0:
                survived += 1
            capital = (capital * i + sim_cap) / (i + 1) if i > 0 else sim_cap
            liquidations += liq

        max_dd = (peak - capital) / peak if peak > 0 else 0
        return StressTestResult(
            scenario="liquidity_collapse",
            portfolio_survived=survived / sims > 0.5,
            forced_liquidations=liquidations,
            kill_switch_activated=kill_switch,
            kill_switch_delay_seconds=kill_delay,
            max_drawdown=max_dd,
            final_capital=capital,
            survived_pct=survived / sims if sims > 0 else 0,
        )

    async def _simulate_correlated_crash(self, sims: int) -> StressTestResult:
        capital = self._initial_capital
        peak = capital
        liquidations = 0
        kill_switch = False
        kill_delay = 30.0
        survived = 0.0

        for i in range(sims):
            trades = await self._fetch_recent_trades(7)
            sim_cap = float(capital)
            corr_shock = random.uniform(-0.6, -0.4)
            liq = 0

            for j, trade in enumerate(trades[:25]):
                pnl_impact = float(trade.pnl or 0) * (1.0 + corr_shock) - abs(float(trade.pnl or 0)) * 0.7
                sim_cap += pnl_impact
                if sim_cap > peak:
                    peak = sim_cap
                if sim_cap <= 0:
                    liq += 1
                    break

            if sim_cap <= capital * 0.3:
                kill_switch = True
            if sim_cap > 0:
                survived += 1
            capital = (capital * i + sim_cap) / (i + 1) if i > 0 else sim_cap
            liquidations += liq

        max_dd = (peak - capital) / peak if peak > 0 else 0
        return StressTestResult(
            scenario="correlated_crash",
            portfolio_survived=survived / sims > 0.5,
            forced_liquidations=liquidations,
            kill_switch_activated=kill_switch,
            kill_switch_delay_seconds=kill_delay,
            max_drawdown=max_dd,
            final_capital=capital,
            survived_pct=survived / sims if sims > 0 else 0,
        )

    async def _simulate_slippage_spike(self, sims: int) -> StressTestResult:
        capital = self._initial_capital
        peak = capital
        liquidations = 0
        kill_switch = False
        kill_delay = 45.0
        survived = 0.0

        for i in range(sims):
            trades = await self._fetch_recent_trades(7)
            sim_cap = float(capital)
            liq = 0
            spike_mult = random.uniform(3.0, 10.0)

            for j, trade in enumerate(trades[:20]):
                base_slip = float(trade.slippage or 0.001)
                slip_cost = base_slip * spike_mult * float(trade.filled_size or trade.size or 0) * 100
                pnl_impact = float(trade.pnl or 0) - slip_cost
                sim_cap += pnl_impact
                if sim_cap > peak:
                    peak = sim_cap
                if sim_cap <= 0:
                    liq += 1
                    break

            if sim_cap <= capital * 0.5:
                kill_switch = True
            if sim_cap > 0:
                survived += 1
            capital = (capital * i + sim_cap) / (i + 1) if i > 0 else sim_cap
            liquidations += liq

        max_dd = (peak - capital) / peak if peak > 0 else 0
        return StressTestResult(
            scenario="slippage_spike",
            portfolio_survived=survived / sims > 0.5,
            forced_liquidations=liquidations,
            kill_switch_activated=kill_switch,
            kill_switch_delay_seconds=kill_delay,
            max_drawdown=max_dd,
            final_capital=capital,
            survived_pct=survived / sims if sims > 0 else 0,
        )

    async def _simulate_delayed_execution(self, sims: int) -> StressTestResult:
        capital = self._initial_capital
        peak = capital
        liquidations = 0
        kill_switch = False
        kill_delay = 90.0
        survived = 0.0

        for i in range(sims):
            trades = await self._fetch_recent_trades(7)
            sim_cap = float(capital)
            delay_seconds = random.choice([1, 3, 5, 10])
            liq = 0

            for j, trade in enumerate(trades[:20]):
                decay = 1.0 - delay_seconds * 0.02
                pnl_impact = float(trade.pnl or 0) * max(0, decay)
                sim_cap += pnl_impact
                if sim_cap > peak:
                    peak = sim_cap
                if sim_cap <= 0:
                    liq += 1
                    break

            if sim_cap <= capital * 0.4:
                kill_switch = True
            if sim_cap > 0:
                survived += 1
            capital = (capital * i + sim_cap) / (i + 1) if i > 0 else sim_cap
            liquidations += liq

        max_dd = (peak - capital) / peak if peak > 0 else 0
        return StressTestResult(
            scenario="delayed_execution",
            portfolio_survived=survived / sims > 0.5,
            forced_liquidations=liquidations,
            kill_switch_activated=kill_switch,
            kill_switch_delay_seconds=kill_delay,
            max_drawdown=max_dd,
            final_capital=capital,
            survived_pct=survived / sims if sims > 0 else 0,
        )

    async def _simulate_spread_widening(self, sims: int) -> StressTestResult:
        capital = self._initial_capital
        peak = capital
        liquidations = 0
        kill_switch = False
        kill_delay = 60.0
        survived = 0.0

        for i in range(sims):
            trades = await self._fetch_recent_trades(7)
            sim_cap = float(capital)
            spread_mult = random.uniform(2.0, 8.0)
            liq = 0

            for j, trade in enumerate(trades[:20]):
                spread_cost = (float(trade.slippage or 0.001) * spread_mult) * float(trade.filled_size or trade.size or 0) * 50
                pnl_impact = float(trade.pnl or 0) - spread_cost
                sim_cap += pnl_impact
                if sim_cap > peak:
                    peak = sim_cap
                if sim_cap <= 0:
                    liq += 1
                    break

            if sim_cap <= capital * 0.4:
                kill_switch = True
            if sim_cap > 0:
                survived += 1
            capital = (capital * i + sim_cap) / (i + 1) if i > 0 else sim_cap
            liquidations += liq

        max_dd = (peak - capital) / peak if peak > 0 else 0
        return StressTestResult(
            scenario="spread_widening",
            portfolio_survived=survived / sims > 0.5,
            forced_liquidations=liquidations,
            kill_switch_activated=kill_switch,
            kill_switch_delay_seconds=kill_delay,
            max_drawdown=max_dd,
            final_capital=capital,
            survived_pct=survived / sims if sims > 0 else 0,
        )

    async def _fetch_recent_trades(self, days: int) -> list[Trade]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(Trade)
            .where(Trade.created_at >= cutoff)
            .order_by(Trade.created_at.desc())
            .limit(100)
        )
        return list(result.scalars().all())
