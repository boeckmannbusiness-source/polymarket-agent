import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

async def run_benchmark(num_mints: int):
    # Setup mocks
    price_svc = MagicMock()
    # Simulate API latency of 100ms
    async def mock_resolve_price(mint):
        await asyncio.sleep(0.1)
        return MagicMock(price=Decimal("1.0"))

    price_svc.resolve_price = mock_resolve_price

    distinct_mints = [f"mint_{i}" for i in range(num_mints)]
    mint_to_price = {}

    print(f"\nBenchmarking {num_mints} mints...")

    # 1. Sequential (Old)
    start_seq = time.monotonic()
    for mint in distinct_mints:
        res = await price_svc.resolve_price(mint)
        if res.price is not None:
            mint_to_price[mint] = float(res.price)
    end_seq = time.monotonic()
    print(f"Sequential duration: {end_seq - start_seq:.2f}s")

    # 2. Parallel (New)
    mint_to_price = {}
    sem = asyncio.Semaphore(10)
    async def resolve_with_sem(m):
        async with sem:
            res = await price_svc.resolve_price(m)
            return m, res

    start_par = time.monotonic()
    results = await asyncio.gather(*[resolve_with_sem(m) for m in distinct_mints])
    for mint, res in results:
        if res.price is not None:
            mint_to_price[mint] = float(res.price)
    end_par = time.monotonic()
    print(f"Parallel (limit 10) duration: {end_par - start_par:.2f}s")

    return end_seq - start_seq, end_par - start_par

async def main():
    s100, p100 = await run_benchmark(100)
    assert p100 < 10.0, "100 mints took too long in parallel"

    s500, p500 = await run_benchmark(500)
    assert p500 < 30.0, "500 mints took too long in parallel"

    print("\nBenchmark results verified.")

if __name__ == "__main__":
    asyncio.run(main())
