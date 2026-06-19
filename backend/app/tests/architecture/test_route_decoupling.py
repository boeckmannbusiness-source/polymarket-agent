import ast
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "app")
EXECUTION_SERVICE_FILE = os.path.join(ROOT, "services", "execution", "execution_service.py")
ROUTE_PLANNER_DIR = os.path.join(ROOT, "services", "planning", "route_planner")
EXCLUDED = {"__pycache__", ".venv", "venv", "env"}

ROUTING_MODULES = {
    "JupiterRoutePlanner",
    "RouteOptimizer",
    "BaseRoutePlanner",
}

FORBIDDEN_EXECUTION_TERMS = {"swap", "signature", "wallet", "private_key", "transaction"}


def _walk_py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def test_execution_service_imports_no_routing_logic():
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
    violations = imported_names & ROUTING_MODULES
    assert not violations, (
        f"ExecutionService imports routing logic directly:\n"
        + "\n".join(f"  {name}" for name in violations)
    )


def test_route_planner_imports_no_adapters():
    for filepath in _walk_py_files(ROUTE_PLANNER_DIR):
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


def test_route_contains_no_execution_logic():
    route_file = os.path.join(ROOT, "domain", "planning", "route.py")
    with open(route_file, encoding="utf-8") as f:
        content = f.read()
    for term in FORBIDDEN_EXECUTION_TERMS:
        if term in content.lower():
            pytest.fail(f"Route model contains execution term: {term}")


def test_no_swap_or_signing_in_route_planner():
    for filepath in _walk_py_files(ROUTE_PLANNER_DIR):
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for term in ("swap", "sign", "wallet", "transaction"):
                        if term in alias.name.lower():
                            pytest.fail(f"{filepath} imports forbidden module: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for term in ("swap", "sign", "wallet", "transaction"):
                        if term in node.module.lower():
                            pytest.fail(f"{filepath} imports forbidden module: {node.module}")


def test_route_is_deterministic_given_same_quote():
    from decimal import Decimal
    from app.domain.execution import Instrument
    from app.domain.planning import Quote, Route
    from app.services.planning.route_planner import JupiterRoutePlanner

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
    planner = JupiterRoutePlanner()

    async def run():
        r1 = await planner.build_route(quote)
        r2 = await planner.build_route(quote)
        assert r1.venue == r2.venue
        assert r1.route_type == r2.route_type
        assert r1.hops == r2.hops
        assert r1.estimated_cost_bps == r2.estimated_cost_bps
        assert r1.price_impact_estimate == r2.price_impact_estimate
        assert r1.estimated_latency_ms == r2.estimated_latency_ms
        return r1

    route = asyncio.run(run())
    assert route.route_type == "DIRECT", f"Expected DIRECT route for low impact, got {route.route_type}"
    assert route.estimated_cost_bps is not None
    assert route.price_impact_estimate == 0.005


def test_route_model_has_upgraded_fields():
    from app.domain.planning import Route

    field_names = set(Route.model_fields.keys())
    for required in ("route_type", "estimated_cost_bps", "price_impact_estimate", "hops"):
        assert required in field_names, f"Route model missing required field: {required}"


def test_route_optimizer_splits_on_high_impact():
    from decimal import Decimal
    from app.domain.execution import Instrument
    from app.domain.planning import Quote
    from app.services.planning.route_planner import RouteOptimizer

    instrument = Instrument(venue="jupiter", symbol="SOL/USDC", asset_identifier="SOL", quote_asset="USDC")
    quote = Quote(
        instrument=instrument,
        amount_in=Decimal("100"),
        expected_amount_out=Decimal("99.5"),
        estimated_price=Decimal("150.0"),
        slippage_bps=50,
        source="jupiter",
        price_impact_estimate=0.05,  # High impact -> should split
        source_latency_ms=45.0,
        liquidity_depth=Decimal("50"),
    )

    route = RouteOptimizer.select_best_route(quote)
    assert route.route_type == "SPLIT", f"Expected SPLIT for high impact, got {route.route_type}"
    assert route.estimated_cost_bps is not None
