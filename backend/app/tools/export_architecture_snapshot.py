import json
import os
import sys
from typing import Any

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.exchanges import ExchangeAdapterRegistry
from app.services.capabilities.capability_registry import capability_registry
from app.domain.execution_authorization.models import ExecutionMode, POLICIES
from app.core.exceptions import StartupSafetyViolation
from app.services.execution.governance.execution_governor import ExecutionAuthorizationError
from app.services.replay.offline_guard import ReplayIsolationViolation

def export_snapshot():
    # Ensure registry is frozen to reflect certified state
    if not getattr(ExchangeAdapterRegistry, "_frozen", False):
        ExchangeAdapterRegistry.freeze()

    snapshot = {
        "metadata": {
            "version": "1.0",
            "purpose": "Sandbox Certification Architecture Snapshot"
        },
        "exchanges": {
            "frozen": getattr(ExchangeAdapterRegistry, "_frozen", False),
            "adapters": list(ExchangeAdapterRegistry._adapters.keys()),
            "metadata": getattr(ExchangeAdapterRegistry, "_metadata", {})
        },
        "capabilities": {
            "venues": {}
        },
        "governance": {
            "execution_modes": [m.value for m in ExecutionMode],
            "policies": {}
        },
        "exceptions": {
            "safety_critical": [
                "StartupSafetyViolation",
                "ExecutionAuthorizationError",
                "ReplayIsolationViolation"
            ]
        },
        "startup_invariants": [
            "EXECUTION_MODE in {simulation, sandbox}",
            "STRICT_LIVE_ENABLED == False",
            "CAPITAL_ENABLED == False",
            "ExchangeAdapterRegistry is frozen"
        ]
    }

    # Capture capabilities
    for venue in capability_registry.list_venues():
        caps = capability_registry.get_capabilities(venue)
        if caps:
            snapshot["capabilities"]["venues"][venue] = sorted(list(caps.supports))

    # Capture policies
    for mode, policy in POLICIES.items():
        snapshot["governance"]["policies"][mode.value] = {
            "allowed_permissions": sorted([p.value for p in policy.allowed_permissions]),
            "requires_explicit_approval": policy.requires_explicit_approval
        }

    output_path = "ARCHITECTURE_SNAPSHOT.json"
    with open(output_path, "w") as f:
        json.dump(snapshot, f, indent=2)

    print(f"Architecture snapshot exported to {output_path}")

if __name__ == "__main__":
    export_snapshot()
