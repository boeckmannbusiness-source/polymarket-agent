import pytest
from unittest.mock import MagicMock, patch
from app.services.capabilities.startup_validation import StartupSafetyValidator
from app.core.exceptions import StartupSafetyViolation

def test_startup_safety_valid_simulation():
    """Prove that SIMULATION mode with capital/live off passes."""
    with patch("app.services.capabilities.startup_validation.settings") as mock_settings:
        mock_settings.EXECUTION_MODE = "simulation"
        mock_settings.STRICT_LIVE_ENABLED = False
        mock_settings.CAPITAL_ENABLED = False

        # Should not raise
        StartupSafetyValidator.validate()

def test_startup_safety_valid_sandbox():
    """Prove that SANDBOX mode with capital/live off passes."""
    with patch("app.services.capabilities.startup_validation.settings") as mock_settings:
        mock_settings.EXECUTION_MODE = "sandbox"
        mock_settings.STRICT_LIVE_ENABLED = False
        mock_settings.CAPITAL_ENABLED = False

        # Should not raise
        StartupSafetyValidator.validate()

def test_startup_safety_invalid_mode():
    """Prove that LIVE mode (or any other mode) triggers violation."""
    with patch("app.services.capabilities.startup_validation.settings") as mock_settings:
        mock_settings.EXECUTION_MODE = "live"
        mock_settings.STRICT_LIVE_ENABLED = False
        mock_settings.CAPITAL_ENABLED = False

        with pytest.raises(StartupSafetyViolation) as excinfo:
            StartupSafetyValidator.validate()
        assert "Invalid EXECUTION_MODE" in str(excinfo.value)

def test_startup_safety_strict_live_violation():
    """Prove that STRICT_LIVE_ENABLED=True triggers violation."""
    with patch("app.services.capabilities.startup_validation.settings") as mock_settings:
        mock_settings.EXECUTION_MODE = "sandbox"
        mock_settings.STRICT_LIVE_ENABLED = True
        mock_settings.CAPITAL_ENABLED = False

        with pytest.raises(StartupSafetyViolation) as excinfo:
            StartupSafetyValidator.validate()
        assert "STRICT_LIVE_ENABLED must be False" in str(excinfo.value)

def test_startup_safety_capital_enabled_violation():
    """Prove that CAPITAL_ENABLED=True triggers violation."""
    with patch("app.services.capabilities.startup_validation.settings") as mock_settings:
        mock_settings.EXECUTION_MODE = "sandbox"
        mock_settings.STRICT_LIVE_ENABLED = False
        mock_settings.CAPITAL_ENABLED = True

        with pytest.raises(StartupSafetyViolation) as excinfo:
            StartupSafetyValidator.validate()
        assert "CAPITAL_ENABLED must be False" in str(excinfo.value)

@pytest.mark.asyncio
async def test_main_lifespan_fail_closed():
    """Prove that FastAPI lifespan aborts on safety violation."""
    from app.main import lifespan
    from fastapi import FastAPI

    app = FastAPI()

    with patch("app.services.capabilities.startup_validation.settings") as mock_settings:
        # Force a violation
        mock_settings.CAPITAL_ENABLED = True

        with pytest.raises(StartupSafetyViolation):
            async with lifespan(app):
                pass # Should never reach here
