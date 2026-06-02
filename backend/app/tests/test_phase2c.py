import pytest
from datetime import datetime, timezone

from app.services.stream.deduplication import EventDeduplicator
from app.services.monitoring.latency_service import LatencyTracker


class TestEventDeduplication:
    def setup_method(self):
        self.dedup = EventDeduplicator(max_size=100)

    def test_returns_false_for_new_event(self):
        event = {"event_id": "abc-123", "type": "fill.created"}
        assert self.dedup.is_duplicate(event) is False

    def test_returns_true_for_duplicate_event_id(self):
        event = {"event_id": "abc-123", "type": "fill.created"}
        self.dedup.is_duplicate(event)
        assert self.dedup.is_duplicate(event) is True

    def test_returns_false_without_event_id(self):
        event = {"type": "fill.created"}
        assert self.dedup.is_duplicate(event) is False

    def test_hit_rate_tracks_correctly(self):
        self.dedup.is_duplicate({"event_id": "1"})
        self.dedup.is_duplicate({"event_id": "2"})
        self.dedup.is_duplicate({"event_id": "1"})
        assert self.dedup.hit_rate == pytest.approx(1 / 3, abs=0.01)

    def test_cache_eviction_under_max_size(self):
        small = EventDeduplicator(max_size=5)
        for i in range(10):
            small.is_duplicate({"event_id": f"evt-{i}"})
        assert small.size == 5

    def test_mark_seen(self):
        self.dedup.mark_seen("existing-id")
        assert self.dedup.is_duplicate({"event_id": "existing-id"}) is True


class TestLatencyTracker:
    def setup_method(self):
        self.tracker = LatencyTracker()

    def test_record_and_summary_single_metric(self):
        for ms in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            self.tracker.record("fill_latency", ms)
        summary = self.tracker.summary("fill_latency")
        assert "fill_latency" in summary
        assert summary["fill_latency"]["count_1m"] > 0
        assert summary["fill_latency"]["p50_1m"] > 0

    def test_percentile_values(self):
        for ms in range(1, 101):
            self.tracker.record("test_metric", ms)
        summary = self.tracker.summary("test_metric")
        assert 45 <= summary["test_metric"]["p50_1m"] <= 55
        assert 90 <= summary["test_metric"]["p95_1m"] <= 100

    def test_record_fill_latency(self):
        import time
        start = time.time()
        self.tracker.record_fill_latency("fill-1", start)
        summary = self.tracker.summary("fill_latency")
        assert summary["fill_latency"]["count_1m"] > 0

    def test_summary_returns_all_metrics_when_no_filter(self):
        self.tracker.record("alpha", 10)
        self.tracker.record("beta", 20)
        summary = self.tracker.summary()
        assert "alpha" in summary
        assert "beta" in summary
