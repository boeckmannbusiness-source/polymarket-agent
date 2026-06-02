import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any


class LatencyTracker:
    def __init__(self, window_1m: int = 60, window_15m: int = 900):
        self._buckets: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=10000))
        self._window_1m = window_1m
        self._window_15m = window_15m

    def record(self, metric: str, latency_ms: float):
        self._buckets[metric].append(latency_ms)

    def _percentile(self, values: list[float], p: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = max(0, min(len(sorted_vals) - 1, int(len(sorted_vals) * p / 100)))
        return sorted_vals[idx]

    def _window_values(self, metric: str, window_seconds: int) -> list[float]:
        now = time.time()
        cutoff = now - window_seconds
        return [v for v in self._buckets.get(metric, []) if v >= 0]

    def summary(self, metric: str | None = None) -> dict[str, Any]:
        if metric:
            metrics = [metric]
        else:
            metrics = list(self._buckets.keys())

        result = {}
        for m in metrics:
            vals_1m = self._window_values(m, self._window_1m)
            vals_15m = self._window_values(m, self._window_15m)

            result[m] = {
                "p50_1m": round(self._percentile(vals_1m, 50), 2),
                "p95_1m": round(self._percentile(vals_1m, 95), 2),
                "p99_1m": round(self._percentile(vals_1m, 99), 2),
                "p50_15m": round(self._percentile(vals_15m, 50), 2),
                "p95_15m": round(self._percentile(vals_15m, 95), 2),
                "p99_15m": round(self._percentile(vals_15m, 99), 2),
                "count_1m": len(vals_1m),
                "count_15m": len(vals_15m),
            }

        return result

    def record_fill_latency(self, fill_id: str, created_at: float, emitted_at: float | None = None):
        emitted = emitted_at or time.time()
        latency_ms = (emitted - created_at) * 1000
        self.record("fill_latency", latency_ms)

    def record_snapshot_latency(self, duration_ms: float):
        self.record("snapshot_generation", duration_ms)

    def record_ws_emission_latency(self, duration_ms: float):
        self.record("ws_emission", duration_ms)

    def record_replay_latency(self, duration_ms: float):
        self.record("replay_query", duration_ms)


latency_tracker = LatencyTracker()
