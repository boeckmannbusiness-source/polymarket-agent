"""PAPER_BURNIN_SHORT mode configuration and detection."""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

_BURNIN_ACTIVE: bool = False
_BURNIN_START: float = 0.0
_BURNIN_MODE: str = ""


def is_burnin_short() -> bool:
    """Check if running in PAPER_BURNIN_SHORT mode."""
    return os.environ.get("PAPER_BURNIN_SHORT") == "1" or _BURNIN_ACTIVE


def get_burnin_mode() -> str:
    """Return 'SHORT', 'EXTENDED', or ''."""
    if not is_burnin_short():
        return ""
    return os.environ.get("PAPER_BURNIN_MODE", "SHORT")


def activate(mode: str = "SHORT"):
    global _BURNIN_ACTIVE, _BURNIN_START, _BURNIN_MODE
    _BURNIN_ACTIVE = True
    _BURNIN_START = datetime.now(timezone.utc).timestamp()
    _BURNIN_MODE = mode
    os.environ["PAPER_BURNIN_SHORT"] = "1"
    os.environ["PAPER_BURNIN_MODE"] = mode


def deactivate():
    global _BURNIN_ACTIVE, _BURNIN_MODE
    _BURNIN_ACTIVE = False
    _BURNIN_MODE = ""
    os.environ.pop("PAPER_BURNIN_SHORT", None)
    os.environ.pop("PAPER_BURNIN_MODE", None)


@dataclass
class BurninConfig:
    mode: str = "SHORT"
    duration_minutes: int = 15
    throttle_strategies: bool = False
    disable_long_window_analytics: bool = True
    high_frequency_evaluation: bool = True
    disable_walk_forward: bool = True
    disable_24h_batch: bool = True
    disable_phase45_analysis: bool = False
    disable_replay_parity: bool = True
    metrics_interval_seconds: int = 60


def get_burnin_config() -> BurninConfig:
    if not is_burnin_short():
        return BurninConfig(mode="", duration_minutes=0, disable_long_window_analytics=False)
    mode = get_burnin_mode()
    return BurninConfig(
        mode=mode,
        duration_minutes=30 if mode == "EXTENDED" else 15,
    )
