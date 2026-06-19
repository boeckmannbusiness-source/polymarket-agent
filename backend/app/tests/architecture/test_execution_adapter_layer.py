import ast
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "app")
EXCLUDED = {"__pycache__", ".venv", "venv", "env"}

ADAPTER_SEARCH_ROOTS = [
    os.path.join(ROOT, "exchanges", "adapters"),
    os.path.join(ROOT, "services", "execution", "simulation"),
]

FORBIDDEN_TERMS = {"solana", "solders", "signature", "signer", "wallet", "private_key"}
# "transaction" omitted intentionally; TransactionPlan/TransactionInstruction are domain models,
# not blockchain imports.


def _walk_py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def test_no_solana_imports_in_adapter_layer():
    for root_dir in ADAPTER_SEARCH_ROOTS:
        if not os.path.isdir(root_dir):
            continue
        for filepath in _walk_py_files(root_dir):
            with open(filepath, encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=filepath)
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for term in FORBIDDEN_TERMS:
                            if term in alias.name.lower():
                                pytest.fail(f"{filepath} imports forbidden module: {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for term in FORBIDDEN_TERMS:
                            if term in node.module.lower():
                                pytest.fail(f"{filepath} imports forbidden module: {node.module}")


def test_no_signing_logic_exists():
    for root_dir in ADAPTER_SEARCH_ROOTS:
        if not os.path.isdir(root_dir):
            continue
        for filepath in _walk_py_files(root_dir):
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            for term in ("sign", "signature", "signer", "wallet", "private_key", "nonce"):
                if term in content.lower():
                    pytest.fail(f"{filepath} contains signing/blockchain term: '{term}'")


def test_execution_adapter_returns_deterministic_results():
    from decimal import Decimal
    from app.domain.execution import Instrument
    from app.domain.planning import Quote, Route, TransactionPlan, ExecutionConstraints, TransactionInstruction
    from app.exchanges.adapters import JupiterExecutionAdapter

    import asyncio

    instrument = Instrument(venue="jupiter", symbol="SOL/USDC", asset_identifier="SOL", quote_asset="USDC")
    quote = Quote(
        instrument=instrument,
        amount_in=Decimal("100"),
        expected_amount_out=Decimal("99.5"),
        estimated_price=Decimal("150.0"),
        slippage_bps=50,
        source="jupiter",
    )
    route = Route(venue="jupiter", hops=["jupiter"], route_type="DIRECT", estimated_cost_bps=5)
    constraints = ExecutionConstraints(max_slippage_bps=50)
    instructions = [
        TransactionInstruction(instruction_type="SWAP", source_asset="SOL", target_asset="USDC", amount=Decimal("100")),
    ]
    plan = TransactionPlan(quote=quote, route=route, constraints=constraints, instructions=instructions, estimated_fees=5000, slippage_bps=50)
    adapter = JupiterExecutionAdapter()

    async def run():
        r1 = await adapter.execute(plan)
        r2 = await adapter.execute(plan)
        return r1, r2

    r1, r2 = asyncio.run(run())
    assert r1.status == r2.status
    assert r1.quantity_executed == r2.quantity_executed
    assert r1.average_price == r2.average_price
    assert r1.simulated == True
    assert r1.execution_path == r2.execution_path


def test_transaction_plan_not_mutated():
    from decimal import Decimal
    from app.domain.execution import Instrument
    from app.domain.planning import Quote, Route, TransactionPlan, ExecutionConstraints, TransactionInstruction
    from app.exchanges.adapters import JupiterExecutionAdapter

    import asyncio
    from copy import deepcopy

    instrument = Instrument(venue="jupiter", symbol="SOL/USDC", asset_identifier="SOL", quote_asset="USDC")
    quote = Quote(
        instrument=instrument,
        amount_in=Decimal("100"),
        expected_amount_out=Decimal("99.5"),
        estimated_price=Decimal("150.0"),
        slippage_bps=50,
        source="jupiter",
    )
    route = Route(venue="jupiter", hops=["jupiter"], route_type="DIRECT")
    constraints = ExecutionConstraints(max_slippage_bps=50)
    instructions = [
        TransactionInstruction(instruction_type="SWAP", source_asset="SOL", target_asset="USDC", amount=Decimal("100")),
    ]
    plan = TransactionPlan(quote=quote, route=route, constraints=constraints, instructions=instructions, estimated_fees=5000, slippage_bps=50)
    plan_copy = plan.model_copy(deep=True)

    adapter = JupiterExecutionAdapter()

    async def run():
        await adapter.execute(plan)
        return plan

    result_plan = asyncio.run(run())
    assert result_plan.quote.amount_in == plan_copy.quote.amount_in
    assert result_plan.instructions[0].amount == plan_copy.instructions[0].amount
    assert result_plan.route.hops == plan_copy.route.hops


def test_execution_is_fully_simulated():
    from decimal import Decimal
    from app.domain.execution import Instrument
    from app.domain.planning import Quote, Route, TransactionPlan, ExecutionConstraints, TransactionInstruction
    from app.exchanges.adapters import JupiterExecutionAdapter

    import asyncio

    instrument = Instrument(venue="jupiter", symbol="SOL/USDC", asset_identifier="SOL", quote_asset="USDC")
    quote = Quote(
        instrument=instrument,
        amount_in=Decimal("100"),
        expected_amount_out=Decimal("99.5"),
        estimated_price=Decimal("150.0"),
        slippage_bps=50,
        source="jupiter",
    )
    route = Route(venue="jupiter", hops=["jupiter"], route_type="DIRECT")
    constraints = ExecutionConstraints(max_slippage_bps=50)
    instructions = [
        TransactionInstruction(instruction_type="SWAP", source_asset="SOL", target_asset="USDC", amount=Decimal("100")),
    ]
    plan = TransactionPlan(quote=quote, route=route, constraints=constraints, instructions=instructions, estimated_fees=5000, slippage_bps=50)
    adapter = JupiterExecutionAdapter()

    async def run():
        return await adapter.execute(plan)

    result = asyncio.run(run())
    assert result.simulated is True
    assert result.fill_model == "slippage_linear"
    assert result.simulated_slippage is not None
    assert result.simulated_latency_ms is not None
    assert result.execution_path is not None
    assert "simulated" not in str(type(result)), "Result type should be ExecutionResult, not a mock"


def test_adapter_has_required_methods():
    from app.exchanges.adapters import JupiterExecutionAdapter

    adapter = JupiterExecutionAdapter()
    assert hasattr(adapter, "execute"), "Adapter must have execute method"
    assert hasattr(adapter, "health_check"), "Adapter must have health_check method"
    assert hasattr(adapter, "get_supported_assets"), "Adapter must have get_supported_assets method"


def test_execution_result_has_simulation_fields():
    from app.domain.execution import ExecutionResult

    field_names = set(ExecutionResult.model_fields.keys())
    for required in ("simulated", "fill_model", "execution_path", "simulated_slippage", "simulated_latency_ms"):
        assert required in field_names, f"ExecutionResult missing field: {required}"
