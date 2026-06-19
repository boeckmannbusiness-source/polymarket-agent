import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.domain.execution import ExecutionResult, FillInfo
from app.domain.portfolio import PortfolioSnapshot, PositionProjection, ExecutionFeedback
from app.services.shadow.shadow_portfolio import ShadowPortfolio
from app.services.shadow.portfolio_projector import PortfolioProjector
from app.services.shadow.execution_feedback_service import ExecutionFeedbackService


def _make_result(fills: list | None = None, **kwargs) -> ExecutionResult:
    return ExecutionResult(
        execution_id=kwargs.get("execution_id", "exec-1"),
        adapter=kwargs.get("adapter", "jupiter_simulated"),
        status=kwargs.get("status", "filled"),
        submitted_at=kwargs.get("submitted_at", datetime.now(timezone.utc)),
        completed_at=kwargs.get("completed_at", datetime.now(timezone.utc)),
        fills=fills or [],
        average_price=kwargs.get("average_price", Decimal("150")),
        quantity_executed=kwargs.get("quantity_executed", Decimal("100")),
        fees=kwargs.get("fees", Decimal("0.5")),
        latency_ms=kwargs.get("latency_ms", 150.0),
        simulated=kwargs.get("simulated", True),
        fill_model=kwargs.get("fill_model", "slippage_linear"),
        execution_path=kwargs.get("execution_path", ["SWAP"]),
        simulated_slippage=kwargs.get("simulated_slippage", 0.005),
        simulated_latency_ms=kwargs.get("simulated_latency_ms", 150.0),
        instruction_trace=kwargs.get("instruction_trace", ["SWAP"]),
        metadata=kwargs.get("metadata", {"trade_id": "trade-1"}),
    )


class TestPortfolioUpdatesAreDeterministic:
    def test_same_result_produces_same_snapshot(self):
        fills = [FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"), fee=Decimal("0.1"))]
        result1 = _make_result(fills=fills)
        result2 = _make_result(fills=fills)

        sp = ShadowPortfolio()
        snap1 = sp.apply(result1)
        snap2 = sp.apply(result2)

        assert snap1.cash_balance == snap2.cash_balance
        assert snap1.positions == snap2.positions
        assert snap1.exposure == snap2.exposure
        assert snap1.realized_pnl == snap2.realized_pnl


class TestExecutionResultAlwaysCreatesFeedback:
    def test_with_fills_generates_feedback(self):
        fills = [FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"), fee=Decimal("0.1"))]
        result = _make_result(fills=fills)

        feedback_service = ExecutionFeedbackService()
        feedback = feedback_service.create(result)

        assert feedback.execution_id == "exec-1"
        assert feedback.result_status == "filled"
        assert feedback.slippage_realized == 50.0
        assert feedback.route_efficiency > 0

    def test_empty_fills_still_generates_feedback(self):
        result = _make_result(fills=[])
        feedback_service = ExecutionFeedbackService()
        feedback = feedback_service.create(result)

        assert feedback.execution_id == "exec-1"
        assert feedback.portfolio_delta == 0.0


class TestNoStateMutation:
    def test_shadow_portfolio_does_not_mutate_result(self):
        fills = [FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"), fee=Decimal("0.1"))]
        result = _make_result(fills=fills)
        original_quantity = result.quantity_executed

        sp = ShadowPortfolio()
        sp.apply(result)

        assert result.quantity_executed == original_quantity

    def test_projector_does_not_mutate_result(self):
        fills = [FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"), fee=Decimal("0.1"))]
        result = _make_result(fills=fills)
        original_status = result.status

        projector = PortfolioProjector()
        projector.project(result)

        assert result.status == original_status


class TestProjectionReproducibility:
    def test_same_input_same_projections(self):
        fills = [FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"), fee=Decimal("0.1"))]
        result = _make_result(fills=fills)
        projector = PortfolioProjector()

        proj1 = projector.project(result)
        proj2 = projector.project(result)

        assert len(proj1) == len(proj2)
        for p1, p2 in zip(proj1, proj2):
            assert p1.quantity_before == p2.quantity_before
            assert p1.quantity_after == p2.quantity_after
            assert p1.estimated_pnl == p2.estimated_pnl


class TestNoAdapterImports:
    """Enforcement: shadow services must not import exchange adapters."""

    def test_shadow_portfolio_imports_no_adapters(self):
        import app.services.shadow.shadow_portfolio as mod
        src = str(mod.__file__)
        with open(src) as f:
            content = f.read()
        assert "ExchangeAdapter" not in content
        assert "BaseExecutionAdapter" not in content

    def test_portfolio_projector_imports_no_adapters(self):
        import app.services.shadow.portfolio_projector as mod
        src = str(mod.__file__)
        with open(src) as f:
            content = f.read()
        assert "ExchangeAdapter" not in content
        assert "BaseExecutionAdapter" not in content

    def test_execution_feedback_service_imports_no_adapters(self):
        import app.services.shadow.execution_feedback_service as mod
        src = str(mod.__file__)
        with open(src) as f:
            content = f.read()
        assert "ExchangeAdapter" not in content
        assert "BaseExecutionAdapter" not in content


class TestNoSolanaImports:
    """Enforcement: shadow services must not import Solana or Jupiter."""

    def test_shadow_services_have_no_solana(self):
        import ast, os
        from app.tests.architecture.test_execution_adapter_layer import FORBIDDEN_TERMS, _walk_py_files
        import app.services.shadow as shadow_pkg
        root = os.path.dirname(os.path.dirname(shadow_pkg.__file__))
        shadow_dir = os.path.join(root, "shadow")
        for filepath in _walk_py_files(shadow_dir):
            with open(filepath) as f:
                try:
                    tree = ast.parse(f.read(), filename=filepath)
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for term in FORBIDDEN_TERMS:
                            if term in alias.name.lower():
                                pytest.fail(f"{filepath} imports forbidden: {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for term in FORBIDDEN_TERMS:
                            if term in node.module.lower():
                                pytest.fail(f"{filepath} imports forbidden: {node.module}")


class TestPortfolioSnapshotsImmutable:
    def test_snapshot_values_preserved(self):
        snap = PortfolioSnapshot(
            portfolio_id="p1",
            timestamp=datetime.now(timezone.utc),
            positions={"SOL": Decimal("10")},
            cash_balance=Decimal("50000"),
            exposure=Decimal("1500"),
            realized_pnl=Decimal("100"),
            unrealized_pnl=Decimal("50"),
        )
        assert snap.portfolio_id == "p1"
        assert snap.cash_balance == Decimal("50000")
        assert snap.positions == {"SOL": Decimal("10")}

    def test_snapshot_copy_does_not_affect_original(self):
        fills = [FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"), fee=Decimal("0.1"))]
        result = _make_result(fills=fills)
        sp = ShadowPortfolio()
        current = PortfolioSnapshot(
            portfolio_id="p1",
            timestamp=datetime.now(timezone.utc),
            positions={},
            cash_balance=Decimal("100000"),
            exposure=Decimal("0"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
        )
        snap1 = sp.apply(result, current)
        snap2 = sp.apply(result, current)
        assert snap1.portfolio_id == snap2.portfolio_id
        assert snap1.cash_balance == snap2.cash_balance

    def test_different_execution_different_snapshot(self):
        fills1 = [FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"), fee=Decimal("0.1"))]
        fills2 = [FillInfo(fill_id="SOL", size=Decimal("20"), price=Decimal("160"), fee=Decimal("0.2"))]
        result1 = _make_result(fills=fills1, execution_id="exec-1")
        result2 = _make_result(fills=fills2, execution_id="exec-2")

        sp = ShadowPortfolio()
        snap1 = sp.apply(result1)
        snap2 = sp.apply(result2)

        assert snap1.cash_balance != snap2.cash_balance
        assert snap1.positions["SOL"] != snap2.positions["SOL"]


class TestFeedbackGeneratedForEveryExecution:
    def test_feedback_for_filled_execution(self):
        result = _make_result(status="filled", fills=[FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"))])
        fs = ExecutionFeedbackService()
        fb = fs.create(result)
        assert fb.result_status == "filled"
        assert fb.execution_id == "exec-1"

    def test_feedback_for_failed_execution(self):
        result = _make_result(status="failed", fills=[])
        fs = ExecutionFeedbackService()
        fb = fs.create(result)
        assert fb.result_status == "failed"

    def test_feedback_for_partial_execution(self):
        result = _make_result(status="partial", fills=[FillInfo(fill_id="SOL", size=Decimal("5"), price=Decimal("150"))])
        fs = ExecutionFeedbackService()
        fb = fs.create(result)
        assert fb.result_status == "partial"


class TestDomainModelFields:
    def test_portfolio_snapshot_has_all_fields(self):
        fields = {"portfolio_id", "timestamp", "positions", "cash_balance", "exposure", "realized_pnl", "unrealized_pnl", "metadata"}
        assert set(PortfolioSnapshot.model_fields.keys()) >= fields

    def test_position_projection_has_all_fields(self):
        fields = {"instrument", "quantity_before", "quantity_after", "avg_price_before", "avg_price_after", "estimated_pnl", "estimated_fees"}
        assert set(PositionProjection.model_fields.keys()) >= fields

    def test_execution_feedback_has_all_fields(self):
        fields = {"execution_id", "result_status", "portfolio_delta", "slippage_realized", "fee_realized", "route_efficiency", "latency_ms"}
        assert set(ExecutionFeedback.model_fields.keys()) >= fields


class TestExecutionServiceExtension:
    def test_service_has_shadow_feedback_loop(self):
        from app.services.execution.execution_service import ExecutionService
        assert hasattr(ExecutionService, "_shadow_feedback_loop")
        assert callable(getattr(ExecutionService, "_shadow_feedback_loop"))
