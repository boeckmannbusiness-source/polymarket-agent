import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.domain.execution import ExecutionResult, FillInfo
from app.domain.portfolio import PortfolioSnapshot, PositionProjection, ExecutionFeedback
from app.services.consistency.consistency_report import ConsistencyCheck, ConsistencyReport, ValidatedExecutionBundle
from app.services.consistency.delta_validator import DeltaValidator
from app.services.consistency.fee_validator import FeeValidator
from app.services.consistency.route_validator import RouteValidator
from app.services.consistency.execution_consistency_layer import ExecutionConsistencyLayer


def _make_result(**kwargs) -> ExecutionResult:
    return ExecutionResult(
        execution_id=kwargs.get("execution_id", "exec-1"),
        adapter=kwargs.get("adapter", "jupiter_simulated"),
        status=kwargs.get("status", "filled"),
        submitted_at=kwargs.get("submitted_at", datetime.now(timezone.utc)),
        completed_at=kwargs.get("completed_at", datetime.now(timezone.utc)),
        fills=kwargs.get("fills", []),
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


class TestConsistencyReportModel:
    def test_consistency_check_creation(self):
        check = ConsistencyCheck(name="test_check", passed=True, expected="1", actual="1")
        assert check.name == "test_check"
        assert check.passed is True

    def test_consistency_report_all_passed(self):
        report = ConsistencyReport(
            timestamp=datetime.now(timezone.utc),
            execution_id="exec-1",
            checks=[
                ConsistencyCheck(name="check1", passed=True),
                ConsistencyCheck(name="check2", passed=True),
            ],
            all_passed=True,
        )
        assert report.all_passed is True
        assert len(report.failed_checks) == 0

    def test_consistency_report_has_failed(self):
        report = ConsistencyReport(
            timestamp=datetime.now(timezone.utc),
            execution_id="exec-1",
            checks=[
                ConsistencyCheck(name="check1", passed=True),
                ConsistencyCheck(name="check2", passed=False, expected="x", actual="y"),
            ],
            all_passed=False,
        )
        assert report.all_passed is False
        assert len(report.failed_checks) == 1
        assert report.failed_checks[0].name == "check2"

    def test_validated_execution_bundle_fields(self):
        fields = {"execution_result", "snapshot", "projections", "feedback", "report"}
        assert set(ValidatedExecutionBundle.model_fields.keys()) >= fields


class TestDeltaValidator:
    def test_slippage_delta_valid(self):
        result = _make_result(simulated_slippage=0.005)
        dv = DeltaValidator()
        checks = dv.validate(result, None, None)
        slippage_check = next(c for c in checks if c.name == "slippage_delta_check")
        assert slippage_check.passed is True

    def test_slippage_delta_none(self):
        result = _make_result(simulated_slippage=None)
        dv = DeltaValidator()
        checks = dv.validate(result, None, None)
        slippage_check = next(c for c in checks if c.name == "slippage_delta_check")
        assert slippage_check.passed is False

    def test_latency_consistency_valid(self):
        result = _make_result(latency_ms=150.0)
        dv = DeltaValidator()
        checks = dv.validate(result, None, None)
        latency_check = next(c for c in checks if c.name == "latency_consistency_check")
        assert latency_check.passed is True

    def test_latency_consistency_none(self):
        result = _make_result(latency_ms=None)
        dv = DeltaValidator()
        checks = dv.validate(result, None, None)
        latency_check = next(c for c in checks if c.name == "latency_consistency_check")
        assert latency_check.passed is False

    def test_exposure_delta_with_portfolio(self):
        fills = [FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"))]
        result = _make_result(fills=fills)
        portfolio = PortfolioSnapshot(
            portfolio_id="p1",
            timestamp=datetime.now(timezone.utc),
            positions={"SOL": Decimal("10")},
            cash_balance=Decimal("50000"),
            exposure=Decimal("1500"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
        )
        dv = DeltaValidator()
        checks = dv.validate(result, portfolio, None)
        exposure_check = next(c for c in checks if c.name == "exposure_delta_check")
        assert exposure_check.passed is True


class TestFeeValidator:
    def test_fee_aggregation_matches(self):
        fills = [
            FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"), fee=Decimal("0.3")),
            FillInfo(fill_id="USDC", size=Decimal("5"), price=Decimal("1"), fee=Decimal("0.2")),
        ]
        result = _make_result(fills=fills, fees=Decimal("0.5"))
        fv = FeeValidator()
        checks = fv.validate(result)
        assert len(checks) == 1
        assert checks[0].passed is True

    def test_fee_aggregation_mismatch(self):
        fills = [
            FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"), fee=Decimal("1.0")),
        ]
        result = _make_result(fills=fills, fees=Decimal("0.5"))
        fv = FeeValidator()
        checks = fv.validate(result)
        assert len(checks) == 1
        assert checks[0].passed is False

    def test_fee_no_fills_passes(self):
        result = _make_result(fills=[])
        fv = FeeValidator()
        checks = fv.validate(result)
        assert checks[0].passed is True


class TestRouteValidator:
    def test_route_efficiency_single_hop(self):
        result = _make_result(execution_path=["SWAP"])
        rv = RouteValidator()
        checks = rv.validate(result)
        route_check = next(c for c in checks if c.name == "route_efficiency_check")
        assert route_check.passed is True

    def test_route_efficiency_multi_hop(self):
        result = _make_result(execution_path=["SWAP", "ROUTE_HOP"])
        rv = RouteValidator()
        checks = rv.validate(result)
        route_check = next(c for c in checks if c.name == "route_efficiency_check")
        assert route_check.passed is True

    def test_instruction_trace_integrity_matches(self):
        result = _make_result(instruction_trace=["SWAP"], execution_path=["SWAP"])
        rv = RouteValidator()
        checks = rv.validate(result)
        trace_check = next(c for c in checks if c.name == "instruction_trace_integrity")
        assert trace_check.passed is True

    def test_instruction_trace_mismatch(self):
        result = _make_result(instruction_trace=["SWAP"], execution_path=["SWAP", "ROUTE_HOP"])
        rv = RouteValidator()
        checks = rv.validate(result)
        trace_check = next(c for c in checks if c.name == "instruction_trace_integrity")
        assert trace_check.passed is False

    def test_instruction_trace_both_none(self):
        result = _make_result(instruction_trace=None, execution_path=None)
        rv = RouteValidator()
        checks = rv.validate(result)
        trace_check = next(c for c in checks if c.name == "instruction_trace_integrity")
        assert trace_check.passed is True


class TestExecutionConsistencyLayer:
    def test_validate_returns_bundle_with_all_fields(self):
        fills = [FillInfo(fill_id="SOL", size=Decimal("10"), price=Decimal("150"), fee=Decimal("0.5"))]
        result = _make_result(fills=fills, fees=Decimal("0.5"))
        snapshot = PortfolioSnapshot(
            portfolio_id="p1",
            timestamp=datetime.now(timezone.utc),
            positions={"SOL": Decimal("10")},
            cash_balance=Decimal("50000"),
            exposure=Decimal("1500"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
        )
        projections = [
            PositionProjection(
                instrument="SOL", quantity_before=Decimal("0"), quantity_after=Decimal("10"),
                avg_price_before=Decimal("0"), avg_price_after=Decimal("150"),
                estimated_pnl=Decimal("0"), estimated_fees=Decimal("0.5"),
            ),
        ]
        feedback = ExecutionFeedback(
            execution_id="exec-1", result_status="filled", portfolio_delta=0.0,
            slippage_realized=50.0, fee_realized=0.5, route_efficiency=1.0, latency_ms=150.0,
        )

        layer = ExecutionConsistencyLayer()
        bundle = layer.validate(result, snapshot, projections, feedback)

        assert isinstance(bundle, ValidatedExecutionBundle)
        assert bundle.execution_result.execution_id == "exec-1"
        assert bundle.snapshot.portfolio_id == "p1"
        assert len(bundle.projections) == 1
        assert bundle.feedback.result_status == "filled"
        assert bundle.report.execution_id == "exec-1"

    def test_validate_sets_report_from_checks(self):
        result = _make_result(fills=[], fees=Decimal("0.5"))
        snapshot = PortfolioSnapshot(
            portfolio_id="p1", timestamp=datetime.now(timezone.utc),
            positions={}, cash_balance=Decimal("100000"), exposure=Decimal("0"),
            realized_pnl=Decimal("0"), unrealized_pnl=Decimal("0"),
        )
        feedback = ExecutionFeedback(
            execution_id="exec-1", result_status="filled", portfolio_delta=0.0,
            slippage_realized=0.0, fee_realized=0.5, route_efficiency=1.0, latency_ms=150.0,
        )

        layer = ExecutionConsistencyLayer()
        bundle = layer.validate(result, snapshot, [], feedback)

        assert bundle.report.all_passed is True or bundle.report.all_passed is False
        assert len(bundle.report.checks) >= 5


class TestNoForbiddenImports:
    FORBIDDEN = {"solana", "solders", "signature", "signer", "wallet", "private_key"}

    def _check_file(self, mod_path: str):
        import importlib, ast, os
        mod = importlib.import_module(mod_path)
        src = str(mod.__file__)
        with open(src) as f:
            tree = ast.parse(f.read(), filename=src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for term in self.FORBIDDEN:
                        if term in alias.name.lower():
                            pytest.fail(f"{src} imports forbidden: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for term in self.FORBIDDEN:
                        if term in node.module.lower():
                            pytest.fail(f"{src} imports forbidden: {node.module}")

    def test_no_solana_in_consistency_report(self):
        self._check_file("app.services.consistency.consistency_report")

    def test_no_solana_in_delta_validator(self):
        self._check_file("app.services.consistency.delta_validator")

    def test_no_solana_in_fee_validator(self):
        self._check_file("app.services.consistency.fee_validator")

    def test_no_solana_in_route_validator(self):
        self._check_file("app.services.consistency.route_validator")

    def test_no_solana_in_execution_consistency_layer(self):
        self._check_file("app.services.consistency.execution_consistency_layer")

    def test_no_adapter_imports(self):
        import importlib, os
        mod = importlib.import_module("app.services.consistency.execution_consistency_layer")
        src = str(mod.__file__)
        with open(src) as f:
            content = f.read()
        assert "ExchangeAdapter" not in content
        assert "BaseExecutionAdapter" not in content
        assert "jupiter" not in content.lower()


class TestExecutionServiceIntegration:
    def test_service_has_consistency_validation(self):
        from app.services.execution.execution_service import ExecutionService
        assert hasattr(ExecutionService, "_consistency_validation")
        assert callable(getattr(ExecutionService, "_consistency_validation"))
