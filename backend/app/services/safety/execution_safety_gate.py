import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    market_id: str = ""
    strategy_id: str = ""
    signal_source: str = ""
    regime: str = ""
    expected_return: float = 0.0
    optimization_weight: float = 0.0
    signal_id: str = ""


@dataclass
class ExecutionDecision:
    allowed: bool
    reason: list[str] = field(default_factory=list)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "BLOCKED"] = "LOW"
    shadow_decision: str = ""  # SHADOW_APPROVED or SHADOW_BLOCKED


class ExecutionSafetyGate:
    def __init__(self):
        self._blocks_total = 0
        self._allowed_total = 0
        self._block_reasons: dict[str, int] = {}

    def _evaluate(self, ctx: ExecutionContext) -> tuple[list[str], str]:
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
            risk_level = "BLOCKED"
            shadow_decision = "SHADOW_BLOCKED"
        else:
            risk_level = "LOW"
            shadow_decision = "SHADOW_APPROVED"

        return reasons, shadow_decision

    def validate(self, ctx: ExecutionContext) -> ExecutionDecision:
        from app.core.system_mode import get_mode_manager

        reasons, shadow_decision = self._evaluate(ctx)

        try:
            mode_mgr = get_mode_manager()
            is_shadow = mode_mgr.is_shadow()
        except Exception:
            is_shadow = False

        if is_shadow:
            self._blocks_total += 1
            for r in reasons:
                base = r.split(":")[0]
                self._block_reasons[base] = self._block_reasons.get(base, 0) + 1

            logger.info(
                "execution_safety_gate_shadow",
                shadow_decision=shadow_decision,
                reasons=reasons,
                market_id=ctx.market_id,
                strategy_id=ctx.strategy_id,
            )
            return ExecutionDecision(
                allowed=False,
                reason=reasons,
                risk_level="BLOCKED" if reasons else "LOW",
                shadow_decision=shadow_decision,
            )

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
