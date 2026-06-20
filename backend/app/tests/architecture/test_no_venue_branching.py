import os
import re

def test_no_venue_branching():
    """
    Architecture test: Fail if manual venue/exchange branching exists outside of the capability layer.
    Patterns to catch:
    if venue ==
    if exchange ==
    match venue
    """
    root_dir = "backend/app"
    exclude_dirs = ["services/capabilities", "domain/capabilities", "tests", "migrations"]

    # We allow it in adapters since they are venue-specific by definition
    exclude_dirs.append("services/execution/adapters")
    exclude_dirs.append("services/planning/providers")

    # Some existing places might have it (e.g. translators), let's see if we should exclude them
    # For Sprint 1.8, we want to move towards capabilities.

    branching_patterns = [
        re.compile(r"if\s+.*\bvenue\b\s*==\s*['\"]"),
        re.compile(r"if\s+.*\bexchange\b\s*==\s*['\"]"),
        re.compile(r"match\s+.*\bvenue\b"),
        re.compile(r"match\s+.*\bexchange\b"),
    ]

    violations = []

    for root, dirs, files in os.walk(root_dir):
        # Skip excluded directories
        if any(exc in root for exc in exclude_dirs):
            continue

        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, "r") as f:
                    for i, line in enumerate(f, 1):
                        for pattern in branching_patterns:
                            if pattern.search(line):
                                violations.append(f"{filepath}:{i}: {line.strip()}")

    if violations:
        print("\nVenue branching violations found:")
        for v in violations:
            print(v)
        # assert not violations, f"Found {len(violations)} venue branching violations"
        # For now, let's just log or make it a soft fail if many exist.
        # But instructions say "Fail if".
        assert not violations, f"Found {len(violations)} venue branching violations"
