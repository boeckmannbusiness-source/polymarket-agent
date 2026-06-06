from dataclasses import dataclass, field
from typing import Literal

from app.core.logging import logger


@dataclass
class ExecutionContext:
    position_size_eur: float
    portfolio_exposure: float
    drawdown: float
    regime_confidence: float = 0.0
    drift_score: float = 0.0
    stability_score: float = 0.0
    control_state: str = ""
    risk_flags: list[str] = field(default_factory=list)


@dataclass
class ExecutionDecision:
    allowed: bool
    reason: list[str] = field(default_factory=list)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "BLOCKED"] = "LOW"


class ExecutionSafetyGate:
    def __init__(self):
        self._blocks_total = 0
        self._allowed_total = 0
        self._block_reasons: dict[str, int] = {}

    def validate(self, ctx: ExecutionContext) -> ExecutionDecision:
        reasons: list[str] = []

        if ctx.position_size_eur > 10:
            reasons.append(f"POSITION_SIZE:{ctx.position_size_eur:.2f}>10")

        if ctx.portfolio_exposure > 0.15:
            reasons.append(f"EXPOSURE:{ctx.portfolio_exposure:.4f}>0.15")

        if ctx.drawdown >= 0.15:
            reasons.append(f"DRAWDOWN:{ctx.drawdown:.4f}>=0.15")

        if ctx.stability_score < 50:
            reasons.append(f"STABILITY_SCORE:{ctx.stability_score:.1f}<50")

        if ctx.drift_score != 0.0 and ctx.drift_score >= 50:
            reasons.append(f"DRIFT_SCORE:{ctx.drift_score:.1f}>=50(HIGH)")

        if ctx.regime_confidence < 0.6:
            reasons.append(f"REGIME_CONFIDENCE:{ctx.regime_confidence:.2f}<0.6")

        for flag in ctx.risk_flags:
            flag_u = flag.upper()
            if flag_u in ("CONTROL_FAILURE", "DATA_UNAVAILABLE", "REGIME_UNSTABLE", "KILL_SWITCH_ACTIVE"):
                reasons.append(f"RISK_FLAG:{flag}")

        if reasons:
            self._blocks_total += 1
            for r in reasons:
                base = r.split(":")[0]
                self._block_reasons[base] = self._block_reasons.get(base, 0) + 1
            risk_level: Literal["LOW", "MEDIUM", "HIGH", "BLOCKED"] = "BLOCKED"
            logger.warning("execution_safety_gate_blocked", reasons=reasons)
            return ExecutionDecision(allowed=False, reason=reasons, risk_level=risk_level)

        self._allowed_total += 1
        return ExecutionDecision(allowed=True, reason=[], risk_level="LOW")

    def get_metrics_snapshot(self) -> dict:
        return {
            "execution_blocks_total": self._blocks_total,
            "execution_allowed_total": self._allowed_total,
            "execution_block_reason_counter": dict(self._block_reasons),
        }

    def reset_metrics(self):
        self._blocks_total = 0
        self._allowed_total = 0
        self._block_reasons.clear()


execution_safety_gate = ExecutionSafetyGate()
