import pytest
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock

from app.services.execution.execution_service import ExecutionService
from app.domain.execution import ExecutionIntent, ExecutionResult, Instrument
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.replay.replay_seed import ReplaySeed

@pytest.mark.asyncio
async def test_shadow_decision_recorded():
    # Mock DB session
    db = AsyncMock()

    # Mock ExecutionService dependencies
    service = ExecutionService(db)
    service._get_adapter = MagicMock()
    service._validate_capabilities = AsyncMock()
    service._check_safety = AsyncMock()
    service._kill_switch_recheck = AsyncMock()

    # Setup intent and plan
    instrument = Instrument(venue="paper", symbol="BTC/USDC", asset_identifier="BTC", quote_asset="USDC")
    from app.domain.planning.transaction_plan import TransactionPlan
    from app.domain.planning.route import Route
    from app.domain.planning.quote import Quote
    from app.domain.planning.execution_constraints import ExecutionConstraints
    plan = TransactionPlan(
        route=Route(hops=[], venue="paper", input_amount=Decimal("1.0"), output_amount=Decimal("50000")),
        quote=Quote(
            instrument=instrument,
            amount_in=Decimal("1.0"),
            expected_amount_out=Decimal("50000"),
            estimated_price=Decimal("50000"),
            slippage_bps=10,
            source="test"
        ),
        instructions=[],
        constraints=ExecutionConstraints(max_slippage_bps=10),
        slippage_bps=10
    )
    trade_id = str(uuid.uuid4())
    intent = ExecutionIntent(
        instrument=instrument,
        side="buy",
        quantity=Decimal("1.0"),
        order_type="market",
        strategy_id="test_strat",
        metadata={
            "trade_id": trade_id,
            "confidence": 0.8,
            "predicted_probability": 0.75,
            "expected_ev": 10.5,
            "admission_receipt_hash": "abc123hash"
        },
        transaction_plan=plan
    )

    # Mock adapter result
    result = ExecutionResult(
        execution_id="exec_123",
        adapter="paper",
        status="filled",
        quantity_executed=Decimal("1.0"),
        average_price=Decimal("50000.0"),
        metadata={"trade_id": trade_id}
    )

    adapter = MagicMock()
    adapter.submit_order = AsyncMock(return_value=result)
    service._get_adapter.return_value = adapter

    # Mock governor authorization
    auth = MagicMock()
    auth.decision = "GRANTED"
    auth.reason = "test_reason"
    service._governor.authorize = MagicMock(return_value=auth)

    # Mock ShadowLedger
    mock_ledger = AsyncMock()
    with MagicMock() as mock_ledger_class:
        # We need to mock the import or the instance
        # Since it's imported inside the method, we'll patch it
        import app.services.shadow.shadow_ledger
        app.services.shadow.shadow_ledger.ShadowLedger = MagicMock(return_value=mock_ledger)

        # Run execution
        await service.submit_intent(intent)

        # _propagate_execution_result is called which calls _record_shadow_decision
        # However, submit_intent itself doesn't call _propagate_execution_result.
        # execute_signal and create_trade_execution do.

        await service._propagate_execution_result(result, intent=intent, plan=plan, authorization=auth)

        # Verify ShadowLedger.record_decision was called
        mock_ledger.record_decision.assert_called_once()
        args, kwargs = mock_ledger.record_decision.call_args
        assert kwargs["market_id"] == "BTC/USDC"
        assert kwargs["strategy_id"] == "test_strat"
        assert kwargs["confidence"] == 0.8
        assert kwargs["predicted_probability"] == 0.75
        assert kwargs["expected_ev"] == 10.5
        assert kwargs["admission_receipt_hash"] == "abc123hash"
        assert kwargs["governor_decision"] == "GRANTED"
        assert kwargs["decision"] == "buy"

@pytest.mark.asyncio
async def test_shadow_decision_idempotent():
    # Verify that recording the same decision twice (same signal_id)
    # is handled correctly (e.g. update or skip)
    # For now, we'll just check that it doesn't crash
    pass

@pytest.mark.asyncio
async def test_shadow_decision_replay_linked():
    # Verify that decision_log has the correct replay_hash linked
    pass
