import ast
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "app")
EXECUTION_SERVICE_FILE = os.path.join(ROOT, "services", "execution", "execution_service.py")
EXCLUDED = {"__pycache__", ".venv", "venv", "env"}

PROVIDER_MODULES = {
    "JupiterQuoteProvider",
    "JupiterPriceFeed",
    "BaseQuoteProvider",
}

FORBIDDEN_IMPORTS = {
    "solana",
    "jupiter.swap",
    "jupiter.transaction",
}


def _walk_py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def test_execution_service_imports_no_price_providers():
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
    violations = imported_names & PROVIDER_MODULES
    assert not violations, (
        f"ExecutionService imports price provider modules directly:\n"
        + "\n".join(f"  {name}" for name in violations)
    )


def test_planner_imports_no_adapters():
    """Re-verifies from prior sprint: Planner must not import exchange adapters."""
    planner_file = os.path.join(ROOT, "services", "planning", "planner.py")
    with open(planner_file, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=planner_file)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "app.exchanges" in alias.name:
                    pytest.fail(f"Planner imports adapter module: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and "app.exchanges" in node.module:
                pytest.fail(f"Planner imports adapter module: {node.module}")


def test_quote_contains_no_polymarket_fields():
    quote_file = os.path.join(ROOT, "domain", "planning", "quote.py")
    with open(quote_file, encoding="utf-8") as f:
        content = f.read()
    for token in ("outcome", "condition_id", "clob", "yes_no", "probability"):
        if token in content:
            pytest.fail(f"Quote model contains Polymarket-specific field: {token}")


def test_no_forbidden_blockchain_imports():
    violations = []
    search_roots = [
        os.path.join(ROOT, "domain", "planning"),
        os.path.join(ROOT, "services", "planning"),
        os.path.join(ROOT, "services", "market_data"),
    ]
    for root_dir in search_roots:
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
                        for forbidden in FORBIDDEN_IMPORTS:
                            if forbidden in alias.name.lower():
                                violations.append((filepath, alias.name, forbidden))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for forbidden in FORBIDDEN_IMPORTS:
                            if forbidden in node.module.lower():
                                violations.append((filepath, node.module, forbidden))
    assert not violations, (
        "Forbidden blockchain imports found:\n"
        + "\n".join(f"  {path}: imports '{imp}' (matches '{rule}')" for path, imp, rule in violations)
    )


def test_price_oracle_is_deterministic_and_cached():
    from app.services.market_data.price_oracle import PriceOracle

    oracle = PriceOracle(ttl_seconds=300)
    oracle.set_price("SOL/USDC", "jupiter", 150.50)
    price = oracle.get_price("SOL/USDC", "jupiter")
    assert price == 150.50, "PriceOracle must return cached price"

    price2 = oracle.get_price("SOL/USDC", "jupiter")
    assert price2 == 150.50, "PriceOracle must be deterministic"

    price3 = oracle.get_price("UNKNOWN", "jupiter")
    assert price3 is None, "PriceOracle must return None for unknown symbol"

    all_prices = oracle.get_all_prices()
    assert ("SOL/USDC", "jupiter") in all_prices
    assert all_prices[("SOL/USDC", "jupiter")] == 150.50

    oracle.clear()
    assert oracle.get_price("SOL/USDC", "jupiter") is None


def test_quote_model_has_enhanced_fields():
    from app.domain.planning import Quote

    field_names = set(Quote.model_fields.keys())
    for required in ("timestamp", "source_latency_ms", "price_impact_estimate", "liquidity_depth", "venue_hint"):
        assert required in field_names, (
            f"Quote model missing required field: {required}"
        )


def test_jupiter_price_feed_no_swap_logic():
    feed_file = os.path.join(ROOT, "services", "planning", "providers", "jupiter_price_feed.py")
    with open(feed_file, encoding="utf-8") as f:
        content = f.read()
    forbidden_terms = ["swap", "transaction", "signature", "wallet", "private_key"]
    for term in forbidden_terms:
        if term in content.lower():
            line_num = None
            for i, line in enumerate(content.splitlines(), 1):
                if term.lower() in line.lower():
                    line_num = i
                    break
            if line_num and "NO swap" not in line and "no swap" not in line.lower():
                pytest.fail(
                    f"JupiterPriceFeed contains forbidden term '{term}' at line {line_num}"
                )
