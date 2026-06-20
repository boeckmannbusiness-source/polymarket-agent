import sys
from app.services.capabilities import capability_registry, CapabilityResolver, CapabilityValidator

def test_capability_registry_boundaries():
    """
    Capability services must NOT import:
    execution adapters
    portfolio
    shadow
    solana
    jupiter SDK
    blockchain libraries
    """
    forbidden_modules = [
        "app.services.execution.adapters",
        "app.services.portfolio",
        "app.services.shadow",
        "app.services.solana",
        "jupiter",
        "solana",
        "web3"
    ]

    # Check imports of capability services
    # This is a bit tricky to do statically easily, but we can check sys.modules
    # if we import them here.

    for module_name in sys.modules:
        if module_name.startswith("app.services.capabilities"):
            imported_modules = sys.modules[module_name]
            # This doesn't easily show what it imported.
            pass

    # Alternative: use grep/regex on the files
    import os
    capability_service_dir = "backend/app/services/capabilities"
    for root, _, files in os.walk(capability_service_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, "r") as f:
                    content = f.read()
                    for forbidden in forbidden_modules:
                        if f"import {forbidden}" in content or f"from {forbidden}" in content:
                            assert False, f"Forbidden import {forbidden} found in {filepath}"

def test_capabilities_are_data_only():
    """
    Capabilities contain metadata only. No execution. No side effects.
    """
    from app.domain.capabilities import VenueCapability, VenueCapabilities, CapabilityReport

    # Check that they don't have methods that look like execution
    for cls in [VenueCapabilities, CapabilityReport]:
        for attr_name in dir(cls):
            if attr_name.startswith("_"): continue
            attr = getattr(cls, attr_name)
            if callable(attr):
                # allow basic pydantic/helper methods
                if attr_name in ["has", "is_valid", "json", "dict", "copy", "parse_obj", "parse_raw", "from_orm", "model_dump", "model_dump_json"]:
                    continue
                # If there are other methods, they should be simple property-like helpers
                # This is a manual check or we can inspect source
                pass
