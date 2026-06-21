import pytest
from app.domain.execution import ExecutionIntent

def test_execution_intent_compatibility_prefix():
    """Verify that all compatibility fields in ExecutionIntent are prefixed with compat_."""
    forbidden_fields = {
        "outcome",
        "condition_id",
        "market_id",
        "trade",
        "trade_id",
        "price",
        "size"
    }

    # We check the fields defined in the model
    fields = ExecutionIntent.model_fields.keys()
    for field in fields:
        assert field not in forbidden_fields, f"Legacy field '{field}' found without 'compat_' prefix in ExecutionIntent"

def test_execution_intent_allows_compat_fields():
    """Verify that ExecutionIntent allows fields prefixed with compat_."""
    from decimal import Decimal
    from app.domain.execution.instrument import Instrument

    inst = Instrument(venue="v", symbol="s", asset_identifier="a", quote_asset="q")
    intent = ExecutionIntent(
        instrument=inst,
        side="buy",
        quantity=Decimal("10"),
        order_type="market"
    )

    # These should be settable due to ConfigDict(extra="allow") or being explicitly defined
    intent.compat_trade = None
    intent.compat_outcome = "YES"

    assert intent.compat_outcome == "YES"
