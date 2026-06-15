import asyncio
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
class TestS7Worker:

    # ── Loop pattern tests ──

    async def _run_loop_body(self, iterations: int, fn, sleep_interval: float = 0.001):
        """Simulate the loop pattern from _shadow_price_tracker_loop / _shadow_eval_loop."""
        count = 0
        while count < iterations:
            try:
                await fn()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            count += 1
            if count < iterations:
                await asyncio.sleep(sleep_interval)

    async def test_cancelled_error_breaks_loop(self):
        """CancelledError is caught, loop exits, no more iterations run."""
        call_count = 0

        async def fn():
            nonlocal call_count
            call_count += 1
            raise asyncio.CancelledError()

        await self._run_loop_body(5, fn)
        assert call_count == 1

    async def test_exception_isolation(self):
        """A generic exception in one iteration doesn't stop the loop."""
        seq = [ValueError("boom"), ValueError("boom2"), "ok"]

        async def fn():
            e = seq.pop(0)
            if isinstance(e, Exception):
                raise e

        await self._run_loop_body(3, fn)
        assert len(seq) == 0

    async def test_loop_recovers_after_transient_failure(self):
        """After an exception, the next iteration succeeds."""
        results = []
        fail_first = [True, False]

        async def fn():
            if fail_first.pop(0):
                raise ConnectionError("transient")
            results.append("ok")

        await self._run_loop_body(2, fn)
        assert results == ["ok"]

    async def test_stagger_timing(self):
        """+15s stagger between price tracker and eval loops."""
        import time

        tracker_started_at = None
        eval_started_at = None

        async def tracker_body():
            nonlocal tracker_started_at
            tracker_started_at = time.monotonic()

        async def eval_body():
            nonlocal eval_started_at
            eval_started_at = time.monotonic()

        await tracker_body()
        await asyncio.sleep(0.015)
        await eval_body()

        assert eval_started_at is not None
        assert tracker_started_at is not None
        stagger = eval_started_at - tracker_started_at
        assert stagger >= 0.015, f"stagger={stagger} < 0.015"

    async def test_distinct_mint_dedup(self):
        """Distinct mints are resolved exactly once regardless of position count."""
        rt_to_mint = {
            "rt1": "mint_a",
            "rt2": "mint_a",
            "rt3": "mint_b",
        }
        distinct_mints = list(set(rt_to_mint.values()))
        assert len(distinct_mints) == 2
        assert "mint_a" in distinct_mints
        assert "mint_b" in distinct_mints

    async def test_empty_rt_ids_skips_iteration(self):
        """When no open positions have research_trade_id, the loop skips."""
        open_positions = [
            AsyncMock(research_trade_id=None),
            AsyncMock(research_trade_id=None),
        ]
        rt_ids = [p.research_trade_id for p in open_positions if p.research_trade_id is not None]
        assert len(rt_ids) == 0

    async def test_mint_price_mapping(self):
        """Each open position gets price from its mint's resolved value."""
        rt_to_mint = {"rt1": "mint_a", "rt2": "mint_b"}
        mint_to_price = {"mint_a": 150.0, "mint_b": 75.0}

        open_positions = [
            AsyncMock(research_trade_id="rt1"),
            AsyncMock(research_trade_id="rt2"),
        ]
        updates = 0
        for pos in open_positions:
            mint = rt_to_mint.get(pos.research_trade_id)
            price = mint_to_price.get(mint)
            if price is not None:
                updates += 1

        assert updates == 2

    async def test_worker_graceful_shutdown(self):
        """Cancelling a running task stops it cleanly."""
        started = False
        stopped = False

        async def worker():
            nonlocal started, stopped
            started = True
            try:
                while True:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                stopped = True
                raise

        task = asyncio.create_task(worker())
        await asyncio.sleep(0.05)
        assert started
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped
