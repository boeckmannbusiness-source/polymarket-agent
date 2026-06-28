import pytest
from unittest.mock import MagicMock, Mock, AsyncMock
from app.utils.sanitization import validate_serializable, sanitize_report_data, ReportIntegrityViolation

def test_mock_rejected():
    data = {"name": "Test", "obj": MagicMock()}
    with pytest.raises(ReportIntegrityViolation) as excinfo:
        validate_serializable(data)
    assert "mock leakage" in str(excinfo.value)

def test_report_serialization():
    data = {"status": "READY", "metrics": {"ev": 10.5, "count": 100}}
    # Should not raise
    sanitize_report_data(data)

def test_runtime_report_integrity():
    class Unserializable:
        pass

    data = {"bad": Unserializable()}
    with pytest.raises(ReportIntegrityViolation) as excinfo:
        validate_serializable(data)
    assert "Non-serializable" in str(excinfo.value)

def test_deep_nesting_sanitization():
    data = {"a": {"b": [{"c": Mock()}]}}
    with pytest.raises(ReportIntegrityViolation):
        validate_serializable(data)
