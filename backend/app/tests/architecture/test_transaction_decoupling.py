import ast
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "app")
EXECUTION_SERVICE_FILE = os.path.join(ROOT, "services", "execution", "execution_service.py")
TRANSACTION_BUILDER_DIR = os.path.join(ROOT, "services", "planning", "transaction_builder")
EXCLUDED = {"__pycache__", ".venv", "venv", "env"}

TRANSACTION_MODULES = {
    "JupiterTransactionBuilder",
    "InstructionBuilder",
}

FORBIDDEN_TERMS = {"solana", "solders", "signature", "signer", "wallet"}


def _walk_py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def test_execution_service_imports_no_transaction_builder():
    with open(EXECUTION_SERVICE_FILE, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=EXECUTION_SERVICE_FILE)
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for alias in node.names:
                    imported_names.add(alias.name)
    violations = imported_names & TRANSACTION_MODULES
    assert not violations, (
        f"ExecutionService imports transaction builder modules directly:\n"
        + "\n".join(f"  {name}" for name in violations)
    )


def test_no_solana_imports_in_transaction_layer():
    for filepath in _walk_py_files(TRANSACTION_BUILDER_DIR):
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


def test_no_adapter_imports_in_transaction_layer():
    for filepath in _walk_py_files(TRANSACTION_BUILDER_DIR):
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "app.exchanges" in alias.name:
                        pytest.fail(f"{filepath} imports adapter module: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and "app.exchanges" in node.module:
                    pytest.fail(f"{filepath} imports adapter module: {node.module}")


def test_transaction_instruction_is_platform_agnostic():
    from app.domain.planning import TransactionInstruction

    instr = TransactionInstruction(
        instruction_type="SWAP",
        source_asset="SOL",
        target_asset="USDC",
        amount=100,
    )
    assert instr.instruction_type == "SWAP"
    assert instr.source_asset == "SOL"
    assert instr.target_asset == "USDC"
    assert instr.amount == 100
    assert not hasattr(instr, "program_id"), "Instruction must not contain Solana-specific fields"
    assert not hasattr(instr, "account_keys"), "Instruction must not contain Solana-specific fields"


def test_transaction_plan_contains_no_execution_logic():
    plan_file = os.path.join(ROOT, "domain", "planning", "transaction_plan.py")
    with open(plan_file, encoding="utf-8") as f:
        content = f.read()
    for term in ("signature", "signer", "wallet", "private_key", "execution"):
        if f" {term} " in content.lower() or f"_{term}" in content.lower() or f"\"{term}" in content.lower():
            pytest.fail(f"TransactionPlan contains execution term: {term}")


def test_determinism_same_input_same_plan():
    from decimal import Decimal
    from app.domain.execution import Instrument
    from app.domain.planning import Quote, Route, ExecutionConstraints
    from app.services.planning.transaction_builder import JupiterTransactionBuilder

    import asyncio

    instrument = Instrument(venue="jupiter", symbol="SOL/USDC", asset_identifier="SOL", quote_asset="USDC")
    quote = Quote(
        instrument=instrument,
        amount_in=Decimal("100"),
        expected_amount_out=Decimal("99.5"),
        estimated_price=Decimal("150.0"),
        slippage_bps=50,
        source="jupiter",
        price_impact_estimate=0.005,
        source_latency_ms=45.0,
        liquidity_depth=Decimal("50000"),
    )
    route = Route(venue="jupiter", hops=["jupiter"], route_type="DIRECT", estimated_cost_bps=5, estimated_latency_ms=45.0)
    constraints = ExecutionConstraints(max_slippage_bps=50)
    builder = JupiterTransactionBuilder()

    async def run():
        p1 = await builder.build(quote, route, constraints)
        p2 = await builder.build(quote, route, constraints)
        return p1, p2

    plan1, plan2 = asyncio.run(run())
    assert len(plan1.instructions) == len(plan2.instructions)
    assert plan1.estimated_fees == plan2.estimated_fees
    assert plan1.slippage_bps == plan2.slippage_bps
    assert plan1.instructions[0].instruction_type == plan2.instructions[0].instruction_type


def test_instruction_builder_supports_direct_and_split():
    from decimal import Decimal
    from app.domain.execution import Instrument
    from app.domain.planning import Quote, Route
    from app.services.planning.transaction_builder import InstructionBuilder

    instrument = Instrument(venue="jupiter", symbol="SOL/USDC", asset_identifier="SOL", quote_asset="USDC")
    quote = Quote(
        instrument=instrument,
        amount_in=Decimal("100"),
        expected_amount_out=Decimal("99.5"),
        estimated_price=Decimal("150.0"),
        slippage_bps=50,
        source="jupiter",
    )

    direct_route = Route(venue="jupiter", hops=["jupiter"], route_type="DIRECT")
    direct_instructions = InstructionBuilder.build_instructions(quote, direct_route)
    assert len(direct_instructions) == 1
    assert direct_instructions[0].instruction_type == "SWAP"

    split_route = Route(
        venue="jupiter", hops=["jupiter", "jupiter"], route_type="SPLIT",
        metadata={"split_1": "50", "split_2": "50"},
    )
    split_instructions = InstructionBuilder.build_instructions(quote, split_route)
    assert len(split_instructions) == 2
    assert split_instructions[0].instruction_type == "ROUTE_HOP"
    assert split_instructions[1].instruction_type == "ROUTE_HOP"


def test_instruction_builder_fee_estimation():
    from app.services.planning.transaction_builder import InstructionBuilder
    from app.domain.planning import TransactionInstruction
    from decimal import Decimal

    single = [TransactionInstruction(instruction_type="SWAP", source_asset="SOL", target_asset="USDC", amount=Decimal("100"))]
    multi = [
        TransactionInstruction(instruction_type="ROUTE_HOP", source_asset="SOL", target_asset="USDC", amount=Decimal("50")),
        TransactionInstruction(instruction_type="ROUTE_HOP", source_asset="SOL", target_asset="USDC", amount=Decimal("50")),
    ]

    assert InstructionBuilder.estimate_total_fees(single) == 5000
    assert InstructionBuilder.estimate_total_fees(multi) > 5000
