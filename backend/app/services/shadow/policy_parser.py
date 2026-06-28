import re
import os
from typing import Dict, Any

def parse_promotion_policy(filepath: str = "SANDBOX_PROMOTION_POLICY.md") -> Dict[str, Any]:
    """
    Parses SANDBOX_PROMOTION_POLICY.md to extract quantitative thresholds.
    """
    if not os.path.exists(filepath):
        # Fallback to defaults if file missing, but log it
        return {
            "min_decisions": 500,
            "min_replay_parity": 0.95,
            "max_brier_score": 0.25
        }

    with open(filepath, "r") as f:
        content = f.read()

    thresholds = {}

    # 1. Decision Volume
    # Look for: Minimum 500 shadow decisions
    match = re.search(r"Minimum (\d+) shadow decisions", content)
    if match:
        thresholds["min_decisions"] = int(match.group(1))

    # 2. Replay Parity
    # Look for: ≥95% replay parity
    match = re.search(r"≥(\d+)% replay parity", content)
    if match:
        thresholds["min_replay_parity"] = int(match.group(1)) / 100.0

    # 3. Confidence Calibration (Brier Score)
    # Look for: Brier Score ≤ 0.25
    match = re.search(r"Brier Score ≤ ([\d\.]+)", content)
    if match:
        thresholds["max_brier_score"] = float(match.group(1))

    return thresholds
