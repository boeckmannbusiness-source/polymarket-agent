from enum import Enum

class ExecutionMode(str, Enum):
    DISABLED = "disabled"
    SIMULATION = "simulation"
    SANDBOX = "sandbox"
    LIVE = "live"
