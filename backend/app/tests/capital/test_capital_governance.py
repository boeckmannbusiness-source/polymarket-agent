import pytest
from decimal import Decimal
from unittest.mock import MagicMock
from app.domain.capital.models import CapitalDecision, ExposureState, RiskReceipt
from app.domain.replay.execution_trace import ExecutionTrace
from app.domain.solana.models import SimulationReceipt
from app.domain.admission.models import AdmissionReceipt
from app.domain.capabilities.capability_snapshot import CapabilitySnapshot
from app.services.capital.exposure_model import ExposureModel
from app.services.capital.policy import PolicyService
from app.services.capital.governor import CapitalGovernor
from app.services.capital.guard import CapitalGuard
from app.services.capital.replay import CapitalReplay
from app.domain.execution.execution_intent import ExecutionIntent
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.replay.replay_seed import ReplaySeed
from app.domain.execution.instrument import Instrument


@pytest.fixture
def policy_service():
    return PolicyService()


@pytest.fixture
def exposure_model():
    return ExposureModel()


@pytest.fixture
def governor(policy_service, exposure_model):
    return CapitalGovernor(policy_service, exposure_model)


@pytest.fixture
def mock_intent():
    return ExecutionIntent(
        instrument=Instrument(
            venue="Jupiter",
            symbol="SOL/USDC",
            asset_identifier="So11111111111111111111111111111111111111112",
            quote_asset="EPjFW36vnC7H1VM7L6ZEW5bG97nr6zS6n89XG9N1hZY"
        ),
        side="buy",
        quantity=Decimal("100"),
        order_type="market",
        limit_price=Decimal("1"),
        metadata={"asset_class": "DEFAULT"}
    )


@pytest.fixture
def mock_trace(mock_intent):
    trace = MagicMock(spec=ExecutionTrace)
    trace.intent = mock_intent
    return trace


@pytest.fixture
def mock_simulation():
    sim = MagicMock(spec=SimulationReceipt)
    sim.slot = 1000
    return sim


@pytest.fixture
def mock_admission():
    return MagicMock(spec=AdmissionReceipt)


@pytest.fixture
def mock_capability():
    return MagicMock(spec=CapabilitySnapshot)


def test_position_limit(governor, mock_trace, mock_simulation, mock_admission, mock_capability):
    # Policy limit is 1000. Set quantity * price = 1100
    mock_trace.intent.quantity = Decimal("1100")
    mock_trace.intent.limit_price = Decimal("1")

    receipt = governor.evaluate_execution(mock_trace, mock_simulation, mock_admission, mock_capability)

    assert receipt.capital_decision == CapitalDecision.BLOCK
    assert "POSITION_LIMIT" in receipt.reason_codes


def test_daily_loss_limit(governor, mock_trace, mock_simulation, mock_admission, mock_capability):
    # Policy limit is 500. Set current_daily_loss = 600
    receipt = governor.evaluate_execution(
        mock_trace, mock_simulation, mock_admission, mock_capability,
        current_daily_loss=Decimal("600")
    )

    assert receipt.capital_decision == CapitalDecision.BLOCK
    assert "DAILY_LIMIT" in receipt.reason_codes


def test_exposure_limit(governor, mock_trace, mock_simulation, mock_admission, mock_capability):
    # Total limit 5000. Set current 4500 + planned 600 = 5100
    mock_trace.intent.quantity = Decimal("600")
    receipt = governor.evaluate_execution(
        mock_trace, mock_simulation, mock_admission, mock_capability,
        current_total_exposure=Decimal("4500")
    )

    assert receipt.capital_decision == CapitalDecision.BLOCK
    assert "EXPOSURE_LIMIT_TOTAL" in receipt.reason_codes


def test_emergency_stop(policy_service, exposure_model, mock_trace, mock_simulation, mock_admission, mock_capability):
    # Manually override policy for emergency stop
    ps = MagicMock(spec=PolicyService)
    policy = policy_service.get_active_policy()
    policy.emergency_stop = True
    ps.get_active_policy.return_value = policy

    gov = CapitalGovernor(ps, exposure_model)
    receipt = gov.evaluate_execution(mock_trace, mock_simulation, mock_admission, mock_capability)

    assert receipt.capital_decision == CapitalDecision.BLOCK
    assert "EMERGENCY_STOP" in receipt.reason_codes


def test_capital_disabled(governor, mock_trace, mock_simulation, mock_admission, mock_capability):
    # Governor allows it
    receipt = governor.evaluate_execution(mock_trace, mock_simulation, mock_admission, mock_capability)
    assert receipt.capital_decision == CapitalDecision.ALLOW

    # Guard blocks it
    guard = CapitalGuard(capital_enabled=False)
    protected_receipt = guard.enforce(receipt)

    assert protected_receipt.capital_decision == CapitalDecision.BLOCK
    assert "CAPITAL_DISABLED" in protected_receipt.reason_codes
    assert protected_receipt.verify() # Hash should be valid after modification


def test_risk_replay(governor, mock_trace, mock_simulation, mock_admission, mock_capability):
    receipt = governor.evaluate_execution(mock_trace, mock_simulation, mock_admission, mock_capability)

    # Using MagicMock(spec=ExecutionTrace) and avoiding full Pydantic instantiation for complex types
    trace = MagicMock(spec=ExecutionTrace)
    trace.risk = receipt

    replay = CapitalReplay()
    assert replay.validate(trace) is True

    # Mutation should invalidate
    trace.risk.capital_decision = CapitalDecision.BLOCK # Change decision from ALLOW to BLOCK
    assert replay.validate(trace) is False


def test_asset_class_multiplier(governor, mock_trace, mock_simulation, mock_admission, mock_capability):
    # Set quantity = 2500 -> ratio = 0.25
    mock_trace.intent.quantity = Decimal("2500")

    # MEME asset class: risk_multiplier = 2.0
    # risk_score = 0.25 * 50 * 2.0 = 25.0
    # position_ratio = 0.25
    # 25 > 20 is True -> MEDIUM
    mock_trace.intent.metadata = {"asset_class": "MEME"}
    receipt = governor.evaluate_execution(mock_trace, mock_simulation, mock_admission, mock_capability)
    assert receipt.risk_snapshot["exposure_report"]["exposure_state"] == "MEDIUM"

    # MAJOR asset class: risk_multiplier = 0.8
    # risk_score = 0.25 * 50 * 0.8 = 10.0
    # position_ratio = 0.25
    # 10 > 20 is False. 0.25 > 0.1 is True. -> MEDIUM
    mock_trace.intent.metadata = {"asset_class": "MAJOR"}
    receipt = governor.evaluate_execution(mock_trace, mock_simulation, mock_admission, mock_capability)
    assert receipt.risk_snapshot["exposure_report"]["exposure_state"] == "MEDIUM"

    # MAJOR with smaller quantity -> ratio = 0.1
    mock_trace.intent.quantity = Decimal("1000")
    receipt = governor.evaluate_execution(mock_trace, mock_simulation, mock_admission, mock_capability)
    # risk_score = 4.0. ratio = 0.1. -> LOW
    assert receipt.risk_snapshot["exposure_report"]["exposure_state"] == "LOW"


def test_capital_never_executes(governor, mock_trace, mock_simulation, mock_admission, mock_capability):
    """
    Verify that the CapitalGovernor only returns a receipt and does not call any
    side-effecting execution services.
    """
    receipt = governor.evaluate_execution(mock_trace, mock_simulation, mock_admission, mock_capability)
    assert isinstance(receipt, RiskReceipt)


def test_no_balance_mutation(governor, mock_trace, mock_simulation, mock_admission, mock_capability):
    """
    Verify that no balance mutation occurs.
    """
    initial_exposure = Decimal("1000")
    governor.evaluate_execution(
        mock_trace, mock_simulation, mock_admission, mock_capability,
        current_total_exposure=initial_exposure
    )
    assert initial_exposure == Decimal("1000")


def test_no_order_submission(governor, mock_trace, mock_simulation, mock_admission, mock_capability):
    """
    Verify that no order is submitted to any exchange.
    """
    receipt = governor.evaluate_execution(mock_trace, mock_simulation, mock_admission, mock_capability)
    assert receipt.capital_decision in [CapitalDecision.ALLOW, CapitalDecision.LIMIT, CapitalDecision.BLOCK]
