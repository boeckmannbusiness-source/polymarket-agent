from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.execution import ExecutionIntent, ExecutionResult, FillInfo, Instrument


def test_execution_returns_execution_result():
    result = ExecutionResult(
        execution_id="test-id",
        adapter="paper",
        status="filled",
        submitted_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        fills=[FillInfo(fill_id="f1", size=Decimal("50"), price=Decimal("0.55"))],
        average_price=Decimal("0.55"),
        quantity_executed=Decimal("50"),
        fees=Decimal("0.05"),
        latency_ms=12.5,
    )
    assert result.execution_id == "test-id"
    assert result.status == "filled"
    assert len(result.fills) == 1
    assert result.average_price == Decimal("0.55")


def test_execution_result_roundtrip():
    result = ExecutionResult(
        execution_id="rt-1",
        adapter="paper",
        status="filled",
        fills=[FillInfo(fill_id="f1", size=Decimal("25"), price=Decimal("0.60"))],
        average_price=Decimal("0.60"),
        quantity_executed=Decimal("25"),
    )
    data = result.model_dump(mode="json")
    restored = ExecutionResult.model_validate(data)
    assert restored.execution_id == result.execution_id
    assert restored.average_price == result.average_price
    assert restored.fills[0].size == result.fills[0].size


def test_execution_result_status_variants():
    for status in ("pending", "submitted", "filled", "partially_filled", "cancelled", "failed"):
        result = ExecutionResult(
            execution_id=str(uuid4()),
            adapter="paper",
            status=status,
        )
        assert result.status == status


def test_execution_result_defaults():
    result = ExecutionResult(
        execution_id=str(uuid4()),
        adapter="test",
        status="pending",
    )
    assert result.fills is None
    assert result.average_price is None
    assert result.quantity_executed is None
    assert result.fees is None
    assert result.latency_ms is None
    assert result.metadata is None


def test_execution_result_has_no_polymarket_fields():
    forbidden = {"outcome", "probability", "condition_id", "clob_asset_id", "yes_no"}
    field_names = set(ExecutionResult.model_fields.keys())
    assert not (field_names & forbidden), (
        f"ExecutionResult contains forbidden fields: {field_names & forbidden}"
    )


def test_fill_info_has_no_polymarket_fields():
    forbidden = {"outcome", "probability", "condition_id", "clob_asset_id", "yes_no"}
    field_names = set(FillInfo.model_fields.keys())
    assert not (field_names & forbidden), (
        f"FillInfo contains forbidden fields: {field_names & forbidden}"
    )


def test_execution_intent_has_no_polymarket_fields():
    forbidden = {"outcome", "probability", "condition_id", "clob_asset_id", "yes_no"}
    field_names = set(ExecutionIntent.model_fields.keys())
    assert not (field_names & forbidden), (
        f"ExecutionIntent contains forbidden fields: {field_names & forbidden}"
    )


def test_instrument_has_no_polymarket_fields():
    forbidden = {"outcome", "probability", "condition_id", "clob_asset_id", "yes_no"}
    field_names = set(Instrument.model_fields.keys())
    assert not (field_names & forbidden), (
        f"Instrument contains forbidden fields: {field_names & forbidden}"
    )


@pytest.mark.asyncio
async def test_base_adapter_contract():
    from app.exchanges.base import BaseExchangeAdapter
    import inspect

    sig = inspect.signature(BaseExchangeAdapter.submit_order)
    params = list(sig.parameters.values())
    # Should accept ExecutionIntent
    param_types = [p.annotation for p in params]
    # Second param (self is first) should be ExecutionIntent
    if len(params) > 1:
        from app.domain.execution import ExecutionIntent as EI
        assert params[1].annotation == EI or str(params[1].annotation) == "ExecutionIntent"


@pytest.mark.asyncio
async def test_execution_adapter_contract():
    from app.exchanges import ExchangeAdapterRegistry
    from app.exchanges.paper import PaperExchangeAdapter

    adapter_cls = ExchangeAdapterRegistry.get("paper")
    assert adapter_cls is PaperExchangeAdapter

    # Verify submit_order returns ExecutionResult
    import inspect
    sig = inspect.signature(PaperExchangeAdapter.submit_order)
    return_annotation = sig.return_annotation
    from app.domain.execution import ExecutionResult as ER
    assert return_annotation == ER or "ExecutionResult" in str(return_annotation)
