import pytest
from decimal import Decimal

from app.domain.execution import Instrument
from app.domain.planning import Quote, Route, TransactionPlan, ExecutionConstraints, TransactionInstruction
from app.services.execution.adapters.jupiter_instruction_simulator import JupiterInstructionSimulator
from app.services.execution.adapters.jupiter_execution_adapter import JupiterExecutionAdapter
from app.services.execution.simulation.fill_model import FillEvent
from app.services.execution.simulation.execution_math import (
    compute_slippage_price,
    compute_fee,
    compute_route_cost,
    aggregate_fees,
    compute_average_price,
    compute_estimated_latency_ms,
)


def _make_plan(instructions: list[TransactionInstruction], route_type: str = "DIRECT") -> TransactionPlan:
    instrument = Instrument(venue="jupiter", symbol="SOL/USDC", asset_identifier="SOL", quote_asset="USDC")
    quote = Quote(
        instrument=instrument,
        amount_in=Decimal("100"),
        expected_amount_out=Decimal("99.5"),
        estimated_price=Decimal("150.0"),
        slippage_bps=50,
        source="jupiter",
    )
    route = Route(venue="jupiter", hops=["jupiter"], route_type=route_type)
    constraints = ExecutionConstraints(max_slippage_bps=50)
    return TransactionPlan(quote=quote, route=route, constraints=constraints, instructions=instructions, estimated_fees=5000, slippage_bps=50)


class TestInstructionExecutionFlow:
    def test_swp_instruction_generates_fill(self):
        instr = TransactionInstruction(instruction_type="SWAP", source_asset="SOL", target_asset="USDC", amount=Decimal("100"))
        plan = _make_plan([instr])
        simulator = JupiterInstructionSimulator()
        fills = simulator.simulate_instructions(plan)

        assert len(fills) == 1
        fill = fills[0]
        assert fill.instruction_type == "SWAP"
        assert fill.source_asset == "SOL"
        assert fill.target_asset == "USDC"
        assert fill.amount_in == Decimal("100")
        assert fill.amount_out > Decimal("0")
        assert fill.price > Decimal("0")
        assert fill.fee > Decimal("0")

    def test_route_hop_splits_correctly(self):
        instructions = [
            TransactionInstruction(instruction_type="ROUTE_HOP", source_asset="SOL", target_asset="USDT", amount=Decimal("50")),
            TransactionInstruction(instruction_type="ROUTE_HOP", source_asset="USDT", target_asset="USDC", amount=Decimal("50")),
        ]
        plan = _make_plan(instructions, route_type="SPLIT")
        simulator = JupiterInstructionSimulator()
        fills = simulator.simulate_instructions(plan)

        assert len(fills) == 2
        for i, fill in enumerate(fills):
            assert fill.instruction_index == i
            assert fill.instruction_type == "ROUTE_HOP"
            assert fill.amount_in == Decimal("50")

    def test_deterministic_execution_output(self):
        instr1 = TransactionInstruction(instruction_type="SWAP", source_asset="SOL", target_asset="USDC", amount=Decimal("100"))
        instr2 = TransactionInstruction(instruction_type="ROUTE_HOP", source_asset="SOL", target_asset="USDT", amount=Decimal("50"))
        plan = _make_plan([instr1, instr2])
        simulator = JupiterInstructionSimulator()

        fills1 = simulator.simulate_instructions(plan)
        fills2 = simulator.simulate_instructions(plan)

        assert len(fills1) == len(fills2)
        for f1, f2 in zip(fills1, fills2):
            assert f1.price == f2.price
            assert f1.fee == f2.fee
            assert f1.slippage_bps == f2.slippage_bps
            assert f1.amount_out == f2.amount_out

    def test_no_mutation_of_transaction_plan(self):
        instr = TransactionInstruction(instruction_type="SWAP", source_asset="SOL", target_asset="USDC", amount=Decimal("100"))
        plan = _make_plan([instr])
        original_instr_count = len(plan.instructions)
        original_amount = plan.instructions[0].amount

        simulator = JupiterInstructionSimulator()
        simulator.simulate_instructions(plan)

        assert len(plan.instructions) == original_instr_count
        assert plan.instructions[0].amount == original_amount

    def test_slippage_applied_correctly(self):
        base_price = Decimal("150.0")
        slippage_bps = 50
        expected = base_price * (Decimal("1") + Decimal("50") / Decimal("10000"))
        result = compute_slippage_price(base_price, slippage_bps)
        assert result == expected

    def test_fees_aggregated_correctly(self):
        fees = [Decimal("0.1"), Decimal("0.2"), Decimal("0.3")]
        assert aggregate_fees(fees) == Decimal("0.6")

    def test_execution_result_completeness(self):
        instr = TransactionInstruction(instruction_type="SWAP", source_asset="SOL", target_asset="USDC", amount=Decimal("100"))
        plan = _make_plan([instr])
        adapter = JupiterExecutionAdapter()
        import asyncio

        async def run():
            return await adapter.execute(plan)

        result = asyncio.run(run())
        assert result.execution_id is not None
        assert result.status == "filled"
        assert len(result.fills) == 1
        assert result.average_price > Decimal("0")
        assert result.quantity_executed > Decimal("0")
        assert result.fees > Decimal("0")
        assert result.latency_ms > 0
        assert result.simulated is True
        assert result.instruction_trace == ["SWAP"]

    def test_fill_event_model_fields(self):
        from datetime import datetime
        fe = FillEvent(
            instruction_index=0,
            instruction_type="SWAP",
            source_asset="SOL",
            target_asset="USDC",
            amount_in=Decimal("100"),
            amount_out=Decimal("99.5"),
            price=Decimal("150.0"),
            fee=Decimal("0.1"),
            slippage_bps=50,
            latency_ms=150.0,
            timestamp=datetime(2026, 6, 19),
        )
        assert fe.instruction_index == 0
        assert fe.amount_out == Decimal("99.5")
        assert fe.slippage_bps == 50

    def test_execution_math_functions(self):
        assert compute_fee(Decimal("1000"), 10) == Decimal("1")
        assert compute_route_cost("DIRECT", ["jupiter"], Decimal("1000")) == Decimal("0.5")
        assert compute_route_cost("SPLIT", ["a", "b"], Decimal("1000")) == Decimal("2")
        plan = _make_plan([
            TransactionInstruction(instruction_type="SWAP", source_asset="SOL", target_asset="USDC", amount=Decimal("100")),
        ])
        assert compute_estimated_latency_ms(plan.instructions) == 150.0
        assert compute_estimated_latency_ms(plan.instructions, base_ms=200, per_instruction_ms=100) == 300.0
