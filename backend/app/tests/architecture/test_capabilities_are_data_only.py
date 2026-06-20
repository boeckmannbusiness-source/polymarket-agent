# Merged into test_capability_registry_boundaries.py or separate file as requested.
# I'll keep it in test_capability_registry_boundaries.py for simplicity or create another one.
import pytest
from app.domain.capabilities import VenueCapability, VenueCapabilities, CapabilityReport

def test_capabilities_are_data_only():
    """
    Capabilities contain metadata only. No execution. No side effects.
    """
    # Verify VenueCapability is just an Enum
    assert issubclass(VenueCapability, str)

    # Verify VenueCapabilities is a frozen Pydantic model (read-only)
    from pydantic import ValidationError
    caps = VenueCapabilities(venue="test", supports={VenueCapability.QUOTE})
    with pytest.raises(ValidationError):
        caps.venue = "new"

    # Verify no complex logic in models
    assert hasattr(caps, "has")
    assert caps.has(VenueCapability.QUOTE)
    assert not caps.has(VenueCapability.EXECUTION)
