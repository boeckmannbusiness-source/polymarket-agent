from datetime import datetime, timezone, timedelta

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.benchmark_price import BenchmarkPrice
from app.models.portfolio import PortfolioSnapshot
from app.core.logging import logger


class BenchmarkService:
    DEFAULT_BENCHMARK = "polymarket_volume_index"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_benchmark_price(
        self,
        price: float,
        benchmark_name: str = DEFAULT_BENCHMARK,
        source: str | None = None,
    ) -> BenchmarkPrice:
        bp = BenchmarkPrice(
            benchmark_name=benchmark_name,
            price=price,
            source=source,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(bp)
        await self.db.flush()
        return bp

    async def get_benchmark_history(
        self,
        benchmark_name: str = DEFAULT_BENCHMARK,
        hours: int = 168,
    ) -> list[BenchmarkPrice]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await self.db.execute(
            select(BenchmarkPrice)
            .where(
                BenchmarkPrice.benchmark_name == benchmark_name,
                BenchmarkPrice.timestamp >= cutoff,
            )
            .order_by(BenchmarkPrice.timestamp)
        )
        return list(result.scalars().all())

    async def compute_alpha_vs_beta(
        self,
        benchmark_name: str = DEFAULT_BENCHMARK,
        hours: int = 168,
    ) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Get portfolio snapshots
        snap_result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.timestamp >= cutoff)
            .order_by(PortfolioSnapshot.timestamp)
        )
        snapshots = list(snap_result.scalars().all())

        # Get benchmark prices
        bench_result = await self.db.execute(
            select(BenchmarkPrice)
            .where(
                BenchmarkPrice.benchmark_name == benchmark_name,
                BenchmarkPrice.timestamp >= cutoff,
            )
            .order_by(BenchmarkPrice.timestamp)
        )
        benchmarks = list(bench_result.scalars().all())

        if not snapshots or not benchmarks:
            return {
                "alpha": 0.0,
                "beta": 0.0,
                "portfolio_return": 0.0,
                "benchmark_return": 0.0,
                "message": "insufficient_data",
            }

        portfolio_start = float(snapshots[0].portfolio_value or 0)
        portfolio_end = float(snapshots[-1].portfolio_value or 0)
        portfolio_return = (portfolio_end - portfolio_start) / portfolio_start if portfolio_start > 0 else 0

        bench_start = float(benchmarks[0].price)
        bench_end = float(benchmarks[-1].price)
        benchmark_return = (bench_end - bench_start) / bench_start if bench_start > 0 else 0

        # Beta: covariance(portfolio_returns, benchmark_returns) / variance(benchmark_returns)
        # We compute period-over-period returns
        snap_prices = [float(s.portfolio_value or 0) for s in snapshots if s.portfolio_value]
        bench_prices = [float(b.price) for b in benchmarks]

        returns_p = []
        returns_b = []
        for i in range(1, min(len(snap_prices), len(bench_prices))):
            if snap_prices[i - 1] > 0 and bench_prices[i - 1] > 0:
                returns_p.append((snap_prices[i] - snap_prices[i - 1]) / snap_prices[i - 1])
                returns_b.append((bench_prices[i] - bench_prices[i - 1]) / bench_prices[i - 1])

        beta = 0.0
        alpha = 0.0
        if returns_b and len(returns_b) > 1:
            n = len(returns_b)
            mean_b = sum(returns_b) / n
            mean_p = sum(returns_p) / n if returns_p else 0
            cov = sum((returns_b[i] - mean_b) * (returns_p[i] - mean_p) for i in range(n)) / n
            var_b = sum((r - mean_b) ** 2 for r in returns_b) / n
            beta = cov / var_b if var_b > 0 else 0
            alpha = portfolio_return - beta * benchmark_return

        return {
            "alpha": round(alpha, 6),
            "beta": round(beta, 4),
            "portfolio_return": round(portfolio_return, 6),
            "benchmark_return": round(benchmark_return, 6),
            "benchmark": benchmark_name,
            "period_hours": hours,
            "observation_count": n if returns_b else 0,
        }

    async def compute_synthetic_benchmark(self) -> float:
        """Compute a synthetic benchmark price based on all active market prices.
        Used as a fallback when no external benchmark is configured.
        """
        from app.models import Market
        from app.models.signal_outcome import SignalOutcome

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        result = await self.db.execute(
            select(SignalOutcome.entry_probability, SignalOutcome.market_id)
            .where(SignalOutcome.entry_timestamp >= cutoff)
            .order_by(SignalOutcome.market_id, SignalOutcome.entry_timestamp.desc())
            .distinct(SignalOutcome.market_id)
        )
        rows = list(result.all())

        if not rows:
            return 0.5

        prices = [float(r.entry_probability) for r in rows if r.entry_probability]
        return sum(prices) / len(prices) if prices else 0.5
