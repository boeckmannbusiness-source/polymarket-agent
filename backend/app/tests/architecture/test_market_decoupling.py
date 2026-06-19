import ast
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "app")
DOMAIN_MARKETS_DIR = os.path.join(ROOT, "domain", "markets")
MARKET_REGISTRY_DIR = os.path.join(ROOT, "services", "market_registry")
EXECUTION_SERVICE_FILE = os.path.join(ROOT, "services", "execution", "execution_service.py")

POLYMARKET_NAMES = {
    "condition_id",
    "clob_asset_id",
    "clob",
    "yes_no",
    "outcome",
    "probability",
    "PolyMarket",
    "PolymarketClobClient",
    "PolymarketLiveAdapter",
}


def _walk_py_files(root):
    excluded = {"__pycache__", ".venv", "venv", "env"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in excluded]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def test_domain_markets_no_polymarket_fields():
    violations = []
    for filepath in _walk_py_files(DOMAIN_MARKETS_DIR):
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        for token in ("outcome", "condition_id", "clob", "yes_no", "probability"):
            if token in content:
                violations.append((filepath, token))
    assert not violations, (
        "Domain market models contain Polymarket-specific fields:\n" +
        "\n".join(f"  {path}: {token}" for path, token in violations)
    )


def test_domain_markets_imports_only_pydantic():
    for filepath in _walk_py_files(DOMAIN_MARKETS_DIR):
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = node.names[0].name if isinstance(node, ast.Import) else node.module
                if module and "pydantic" not in module and "app.domain" not in module:
                    pytest.fail(
                        f"{filepath} imports non-domain dependency: {module}"
                    )


def test_market_registry_imports_no_exchange_code():
    for filepath in _walk_py_files(MARKET_REGISTRY_DIR):
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "exchange" in alias.name:
                        pytest.fail(f"{filepath} imports exchange code: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and "exchange" in node.module:
                    pytest.fail(f"{filepath} imports exchange code: {node.module}")


def test_market_registry_no_polymarket_references():
    for filepath in _walk_py_files(MARKET_REGISTRY_DIR):
        if "\\translators\\" in filepath or "/translators/" in filepath:
            continue
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)
        names_in_ast = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names_in_ast.add(node.id)
        for token in POLYMARKET_NAMES:
            if token in names_in_ast or token in content:
                pytest.fail(
                    f"{filepath} references '{token}' directly. "
                    "Market registry domain must be Polymarket-agnostic."
                )


def test_market_registry_imports_domain_only():
    for filepath in _walk_py_files(MARKET_REGISTRY_DIR):
        if filepath.endswith("__init__.py"):
            continue
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        allowed_prefixes = (
            "abc",
            "app.domain",
            "app.services.market_registry",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and not any(node.module.startswith(p) for p in allowed_prefixes):
                    pytest.fail(
                        f"{filepath} imports from outside domain/market_registry: {node.module}"
                    )


def test_execution_service_has_resolve_instrument():
    with open(EXECUTION_SERVICE_FILE, encoding="utf-8") as f:
        content = f.read()
    assert "async def resolve_instrument" in content, (
        "ExecutionService must have resolve_instrument method for market resolution"
    )
    assert "from app.services.market_registry import MarketRegistry" in content or \
           "from app.services.market_registry" in content, (
        "ExecutionService must import MarketRegistry"
    )


def test_execution_service_resolve_creates_valid_instrument():
    from app.services.execution.execution_service import ExecutionService
    import inspect

    sig = inspect.signature(ExecutionService.resolve_instrument)
    params = list(sig.parameters.keys())
    for required in ("venue", "symbol"):
        assert required in params, (
            f"resolve_instrument missing required parameter '{required}'. Got: {params}"
        )


def test_market_translator_only_polymarket_bridge():
    translator_dir = os.path.join(MARKET_REGISTRY_DIR, "translators")
    for filepath in _walk_py_files(translator_dir):
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)
        polymarket_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "polymarket" in alias.name.lower():
                        polymarket_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "polymarket" in node.module.lower():
                    polymarket_imports.append(node.module)
        class_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_names.add(node.name)
        has_polymarket_in_name = any("polymarket" in n.lower() for n in class_names)
        if not polymarket_imports and not has_polymarket_in_name:
            pytest.fail(
                f"{filepath} does not reference Polymarket. "
                "Market translators should explicitly handle Polymarket bridging."
            )


def test_no_translator_imports_exchange_modules():
    translator_dir = os.path.join(MARKET_REGISTRY_DIR, "translators")
    if not os.path.isdir(translator_dir):
        pytest.skip("No translators directory")
    for filepath in _walk_py_files(translator_dir):
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "app.exchanges" in alias.name:
                        pytest.fail(f"{filepath} imports exchange module: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and "app.exchanges" in node.module:
                    pytest.fail(f"{filepath} imports exchange module: {node.module}")
