import pytest
from app.domain.capabilities import VenueCapability
from app.services.capabilities import CapabilityValidator, validate_all, CapabilityRegistrationError

def test_capability_coverage_complete():
    """
    Architecture test: every VenueCapability must have validation logic.
    """
    # This should pass as I updated CapabilityValidator to cover all
    validate_all()

def test_orphan_capability():
    """Fail if a capability exists but is not covered by validator."""
    # We can't easily add to Enum at runtime in a clean way for a test,
    # but we can mock covered_capabilities to return a subset.

    from unittest.mock import patch
    with patch.object(CapabilityValidator, 'covered_capabilities', return_value=[]):
        with pytest.raises(CapabilityRegistrationError, match="has no validation logic"):
            validate_all()
