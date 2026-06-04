import asyncio
import pytest
from app.services.incidents.incident_service import IncidentService


_event_loop = None


def get_loop():
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
    return _event_loop


class TestCircuitBreaker:
    def test_register_and_get_active_empty(self):
        from app.services.risk.circuit_breakers import CircuitBreakerSystem, CircuitBreaker
        cb = CircuitBreakerSystem()
        assert cb._breakers == {}

    def test_register_breaker(self):
        from app.services.risk.circuit_breakers import CircuitBreakerSystem, CircuitBreaker
        cb = CircuitBreakerSystem()
        breaker = CircuitBreaker("test_breaker", lambda: (False, ""), cooldown=60)
        cb.register(breaker)
        assert "test_breaker" in cb._breakers

    def test_get_action_returns_callable(self):
        from app.services.risk.circuit_breakers import CircuitBreakerSystem
        cb = CircuitBreakerSystem()
        action = cb._get_action("loss_circuit")
        assert callable(action)

    def test_get_action_returns_none_for_unknown(self):
        from app.services.risk.circuit_breakers import CircuitBreakerSystem
        cb = CircuitBreakerSystem()
        assert cb._get_action("unknown") is None

    def test_register_default_breakers(self):
        from app.services.risk.circuit_breakers import register_default_breakers, cb_system
        register_default_breakers()
        assert len(cb_system._breakers) >= 4


class TestExecutionSafety:
    def test_safety_error_importable(self):
        from app.services.execution.execution_service import ExecutionSafetyError
        exc = ExecutionSafetyError("test")
        assert str(exc) == "test"


class TestIncidentService:
    def setup_method(self):
        loop = get_loop()
        self.svc = IncidentService()

    def _run(self, coro):
        return get_loop().run_until_complete(coro)

    def test_create_and_get(self):
        inc = self._run(self.svc.create_from_alert({
            "id": "alert-1", "title": "Test alert", "message": "Test message",
            "severity": "critical", "entity_id": "portfolio", "rule": "drawdown_breach",
        }))
        assert inc["title"] == "Test alert"
        assert inc["severity"] == "critical"
        assert inc["status"] == "open"
        assert inc["source"] == "alert"

    def test_create_from_breaker(self):
        inc = self._run(self.svc.create_from_breaker({
            "name": "loss_circuit", "reason": "Daily loss exceeded",
        }))
        assert "loss_circuit" in inc["title"]
        assert inc["severity"] == "critical"

    def test_update_status_to_resolved(self):
        inc = self._run(self.svc.create_from_alert({
            "id": "alert-2", "title": "T", "message": "M",
            "severity": "info", "entity_id": "x", "rule": "test",
        }))
        ok = self._run(self.svc.update_status(inc["id"], "resolved"))
        assert ok is True
        updated = self._run(self.svc.get(inc["id"]))
        assert updated["status"] == "resolved"
        assert updated["resolved_at"] is not None

    def test_update_status_invalid_returns_false(self):
        ok = self._run(self.svc.update_status("nonexistent", "resolved"))
        assert ok is False

    def test_link_trade(self):
        inc = self._run(self.svc.create_from_alert({
            "id": "alert-3", "title": "T", "message": "M",
            "severity": "info", "entity_id": "x", "rule": "test",
        }))
        ok = self._run(self.svc.link_trade(inc["id"], "trade-123"))
        assert ok is True
        updated = self._run(self.svc.get(inc["id"]))
        assert "trade-123" in updated["linked_trades"]

    def test_link_alert(self):
        inc = self._run(self.svc.create_from_alert({
            "id": "alert-4", "title": "T", "message": "M",
            "severity": "info", "entity_id": "x", "rule": "test",
        }))
        ok = self._run(self.svc.link_alert(inc["id"], "other-alert"))
        assert ok is True
        updated = self._run(self.svc.get(inc["id"]))
        assert "other-alert" in updated["linked_alerts"]

    def test_get_stats_empty(self):
        stats = self._run(self.svc.get_stats())
        assert stats["total"] >= 0
        assert "open" in stats

    def test_get_stats_with_incidents(self):
        self._run(self.svc.create_from_alert({
            "id": "alert-5", "title": "A", "message": "B",
            "severity": "critical", "entity_id": "x", "rule": "test",
        }))
        stats = self._run(self.svc.get_stats())
        assert stats["total"] >= 1
