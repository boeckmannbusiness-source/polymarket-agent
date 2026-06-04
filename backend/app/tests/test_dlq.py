import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from app.services.reliability.dead_letter_queue import DeadLetterQueue


class TestDeadLetterQueue:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.dlq = DeadLetterQueue()
        self.dlq._local_backlog.clear()

    async def test_push_stores_locally(self):
        await self.dlq.push("test_domain", "test_event", {"key": "value"}, "test error")
        events = await self.dlq.get_events()
        assert len(events) >= 1
        match = next((e for e in events if e.get("domain") == "test_domain"), None)
        assert match is not None
        assert match["event_type"] == "test_event"
        assert match["error"] == "test error"

    async def test_push_multiple_domains(self):
        await self.dlq.push("domain_a", "evt1", {}, "err1")
        await self.dlq.push("domain_b", "evt2", {}, "err2")
        events = await self.dlq.get_events()
        domains = {e["domain"] for e in events if "domain" in e}
        assert "domain_a" in domains
        assert "domain_b" in domains

    async def test_get_events_filters_by_domain(self):
        await self.dlq.push("domain_a", "evt_a", {}, "err_a")
        await self.dlq.push("domain_b", "evt_b", {}, "err_b")
        events_a = await self.dlq.get_events(domain="domain_a")
        assert all(e["domain"] == "domain_a" for e in events_a)

    async def test_replay_with_callback(self):
        callback = AsyncMock()
        self.dlq.register_callback("test_domain", callback)
        await self.dlq.push("test_domain", "test_event", {"key": "value"}, "test error")
        with patch.object(self.dlq, "_safe_redis", return_value=None):
            result = await self.dlq.replay(domain="test_domain", limit=10)
        callback.assert_called()

    async def test_replay_without_callback_skips(self):
        await self.dlq.push("other_domain", "test_event", {"key": "value"}, "test error")
        with patch.object(self.dlq, "_safe_redis", return_value=None):
            result = await self.dlq.replay(domain="other_domain", limit=10)
        assert result["skipped"] >= 1

    async def test_purge_expired_cleans_old(self):
        old_entry = {
            "domain": "old",
            "event_type": "old_event",
            "payload": "{}",
            "error": "old",
            "retry_count": 0,
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        }
        self.dlq._local_backlog.append(old_entry)
        with patch.object(self.dlq, "_safe_redis", return_value=None):
            await self.dlq.purge_expired(max_age_hours=24)
            events = await self.dlq.get_events()
        assert len(events) == 0

    async def test_stats_returns_counts(self):
        await self.dlq.push("domain_a", "evt1", {}, "err1")
        await self.dlq.push("domain_a", "evt2", {}, "err2")
        stats = await self.dlq.get_stats()
        assert stats["total_events"] > 0
        assert "domain_a" in stats["by_domain"]

    async def test_retry_one_nonexistent(self):
        with patch.object(self.dlq, "_safe_redis", return_value=None):
            result = await self.dlq.retry_one("nonexistent-id")
        assert result is False
