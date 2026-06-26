import uuid
from decimal import Decimal
from typing import List, Dict, Any
from app.domain.capital.models import CapitalDecision, RiskReceipt, CapitalPolicy, ExposureState
from app.domain.replay.execution_trace import ExecutionTrace
from app.domain.solana.models import SimulationReceipt
from app.domain.admission.models import AdmissionReceipt
from app.domain.capabilities.capability_snapshot import CapabilitySnapshot
from app.services.capital.exposure_model import ExposureModel
from app.services.capital.policy import PolicyService


class CapitalGovernor:
    def __init__(self, policy_service: PolicyService, exposure_model: ExposureModel):
        self.policy_service = policy_service
        self.exposure_model = exposure_model

    def evaluate_execution(
        self,
        trace: ExecutionTrace,
        simulation: SimulationReceipt,
        admission: AdmissionReceipt,
        capability: CapabilitySnapshot,
        current_daily_loss: Decimal = Decimal("0"),
        current_total_exposure: Decimal = Decimal("0"),
        current_asset_exposure: Decimal = Decimal("0"),
        total_available_capital: Decimal = Decimal("10000") # Mock capital for simulation
    ) -> RiskReceipt:
        policy = self.policy_service.get_active_policy()
        reason_codes = []
        decision = CapitalDecision.ALLOW

        # 1. Emergency Stop
        if policy.emergency_stop:
            decision = CapitalDecision.BLOCK
            reason_codes.append("EMERGENCY_STOP")

        # 2. Position Size Limit
        planned_position = trace.intent.quantity * (trace.intent.limit_price or Decimal("1"))
        if planned_position > policy.max_position_size:
            decision = CapitalDecision.BLOCK
            reason_codes.append("POSITION_LIMIT")

        # 3. Daily Loss Limit
        if current_daily_loss > policy.max_daily_loss:
            decision = CapitalDecision.BLOCK
            reason_codes.append("DAILY_LIMIT")

        # 4. Exposure Limits
        if current_total_exposure + planned_position > policy.max_total_exposure:
            decision = CapitalDecision.BLOCK
            reason_codes.append("EXPOSURE_LIMIT_TOTAL")

        if current_asset_exposure + planned_position > policy.max_asset_exposure:
            decision = CapitalDecision.BLOCK
            reason_codes.append("EXPOSURE_LIMIT_ASSET")

        # 5. Exposure Model Scoring
        asset_class = trace.intent.metadata.get("asset_class", "DEFAULT") if trace.intent.metadata else "DEFAULT"
        exposure_report = self.exposure_model.calculate_exposure(
            planned_position=planned_position,
            total_capital=total_available_capital,
            simulated_risk=Decimal("50.0"), # Mock risk score
            asset_class=asset_class
        )

        if exposure_report.exposure_state == ExposureState.REJECT:
            decision = CapitalDecision.BLOCK
            reason_codes.append("EXPOSURE_MODEL_REJECT")
        elif exposure_report.exposure_state == ExposureState.HIGH and decision == CapitalDecision.ALLOW:
            decision = CapitalDecision.LIMIT
            reason_codes.append("EXPOSURE_MODEL_HIGH")

        # Snapshot of relevant data for replay
        risk_snapshot = {
            "planned_position": str(planned_position),
            "current_daily_loss": str(current_daily_loss),
            "current_total_exposure": str(current_total_exposure),
            "current_asset_exposure": str(current_asset_exposure),
            "exposure_report": exposure_report.model_dump(mode='json'),
            "policy": policy.model_dump(mode='json'),
            "asset_class": asset_class
        }

        receipt = RiskReceipt(
            risk_id=str(uuid.uuid4()),
            capital_decision=decision,
            policy_version=policy.policy_version,
            risk_snapshot=risk_snapshot,
            reason_codes=reason_codes,
            created_slot=simulation.slot,
            valid_until_slot=simulation.slot + 100,
            risk_hash=""
        )
        receipt.risk_hash = receipt.calculate_hash()

        return receipt
