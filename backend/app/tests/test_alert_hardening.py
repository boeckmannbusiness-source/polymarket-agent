import pytest
from app.services.alerts.alert_service import AlertService


@pytest.fixture
def alert_service():
    svc = AlertService()
    svc._rules = []
    return svc


class TestAlertServiceSync:
    def test_acknowledge_updates_status(self, alert_service):
        alert_service._alert_history = [
            {"id": "alert-1", "status": "triggered", "acknowledged": False,
             "severity": "info", "entity_id": "test", "rule": "test"}
        ]
        assert alert_service.acknowledge("alert-1") is True
        assert alert_service._alert_history[0]["acknowledged"] is True
        assert alert_service._alert_history[0]["status"] == "acknowledged"

    def test_acknowledge_returns_false_for_missing(self, alert_service):
        assert alert_service.acknowledge("nonexistent") is False

    def test_dismiss_updates_status(self, alert_service):
        alert_service._alert_history = [
            {"id": "alert-1", "status": "triggered", "acknowledged": False, "severity": "info", "entity_id": "x", "rule": "x"}
        ]
        assert alert_service.dismiss("alert-1") is True
        assert alert_service._alert_history[0]["status"] == "resolved"

    def test_dismiss_returns_false_for_missing(self, alert_service):
        assert alert_service.dismiss("nonexistent") is False

    def test_resolve_all_for_entity(self, alert_service):
        alert_service._alert_history = [
            {"id": "a1", "status": "triggered", "acknowledged": False, "entity_id": "entity_x", "severity": "info", "rule": "test"},
            {"id": "a2", "status": "acknowledged", "acknowledged": True, "entity_id": "entity_x", "severity": "warning", "rule": "test"},
            {"id": "a3", "status": "triggered", "acknowledged": False, "entity_id": "entity_y", "severity": "info", "rule": "test"},
        ]
        alert_service.resolve_all_for_entity("entity_x")
        assert alert_service._alert_history[0]["status"] == "resolved"
        assert alert_service._alert_history[1]["status"] == "resolved"
        assert alert_service._alert_history[2]["status"] == "triggered"

    def test_get_stats(self, alert_service):
        alert_service._alert_history = [
            {"id": "1", "severity": "info", "status": "triggered", "acknowledged": False},
            {"id": "2", "severity": "warning", "status": "acknowledged", "acknowledged": True},
            {"id": "3", "severity": "critical", "status": "triggered", "acknowledged": False},
        ]
        stats = alert_service.get_stats()
        assert stats["total"] == 3
        assert stats["by_severity"]["info"] == 1
        assert stats["by_severity"]["warning"] == 1
        assert stats["by_severity"]["critical"] == 1
        assert stats["unacknowledged"] == 2

    def test_get_history_filters_by_severity(self, alert_service):
        alert_service._alert_history = [
            {"id": "1", "severity": "info", "status": "triggered", "acknowledged": False},
            {"id": "2", "severity": "warning", "status": "triggered", "acknowledged": False},
            {"id": "3", "severity": "info", "status": "triggered", "acknowledged": False},
        ]
        history = alert_service.get_history(severity="info")
        assert len(history) == 2

    def test_get_history_respects_limit(self, alert_service):
        alert_service._alert_history = [
            {"id": str(i), "severity": "info", "status": "triggered", "acknowledged": False}
            for i in range(20)
        ]
        history = alert_service.get_history(limit=5)
        assert len(history) == 5

    def test_get_unacknowledged_filters_correctly(self, alert_service):
        alert_service._alert_history = [
            {"id": "1", "severity": "info", "status": "triggered", "acknowledged": False},
            {"id": "2", "severity": "warning", "status": "acknowledged", "acknowledged": True},
            {"id": "3", "severity": "critical", "status": "triggered", "acknowledged": False},
        ]
        unack = alert_service.get_unacknowledged()
        assert len(unack) == 2
        assert all(not a["acknowledged"] for a in unack)

    def test_get_unacknowledged_returns_empty_when_all_acknowledged(self, alert_service):
        alert_service._alert_history = [
            {"id": "1", "severity": "info", "status": "acknowledged", "acknowledged": True},
        ]
        assert len(alert_service.get_unacknowledged()) == 0

    def test_register_default_rules(self, alert_service):
        alert_service.register_default_rules()
        assert len(alert_service._rules) > 0

    def test_severity_escalation_logic(self, alert_service):
        from app.services.alerts.rules import AlertRule
        info_rule = AlertRule(name="test_rule", severity="info", alert_type="system", description="t",
                               evaluate=lambda ctx: [], cooldown_seconds=300)
        warning_rule = AlertRule(name="test_rule2", severity="info", alert_type="system", description="t",
                                  evaluate=lambda ctx: [], cooldown_seconds=300)
        alert_service._escalation_counts["test_rule:entity_x"] = 6
        assert alert_service._get_effective_severity(info_rule, "entity_x") == "critical"

        alert_service._escalation_counts["test_rule2:entity_y"] = 3
        assert alert_service._get_effective_severity(warning_rule, "entity_y") == "warning"
