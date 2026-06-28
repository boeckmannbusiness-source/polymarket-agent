from typing import Any, Dict, List, Union
import json
from unittest.mock import Mock

class ReportIntegrityViolation(Exception):
    """Raised when a report contains non-serializable or test-double objects."""
    pass

def validate_serializable(data: Any, path: str = "root"):
    """
    Recursively validates that data is primitive/serializable and does not contain Mocks.
    """
    if isinstance(data, Mock) or "MagicMock" in str(type(data)) or "AsyncMock" in str(type(data)):
        raise ReportIntegrityViolation(f"Runtime mock leakage detected at {path}: {type(data)}")

    if isinstance(data, dict):
        for k, v in data.items():
            validate_serializable(v, f"{path}.{k}")
    elif isinstance(data, (list, tuple)):
        for i, item in enumerate(data):
            validate_serializable(item, f"{path}[{i}]")
    elif data is None or isinstance(data, (str, int, float, bool)):
        return
    else:
        # Check if it's a Pydantic model
        if hasattr(data, "model_dump"):
            validate_serializable(data.model_dump(), path)
        else:
            # Final check via JSON serialization attempt
            try:
                json.dumps(data)
            except (TypeError, OverflowError):
                raise ReportIntegrityViolation(f"Non-serializable object at {path}: {type(data)}")

def sanitize_report_data(data: Any) -> Any:
    """
    Validates data and returns it if safe.
    """
    validate_serializable(data)
    return data
