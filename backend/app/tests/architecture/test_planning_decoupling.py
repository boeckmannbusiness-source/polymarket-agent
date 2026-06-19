import ast
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "app")
PLANNING_DOMAIN_DIR = os.path.join(ROOT, "domain", "planning")
PLANNING_SERVICE_DIR = os.path.join(ROOT, "services", "planning")
EXECUTION_SERVICE_FILE = os.path.join(ROOT, "services", "execution", "execution_service.py")
EXCLUDED = {"__pycache__", ".venv", "venv", "env"}

PLANNING_INTERNALS = {
    "QuoteProvider",
    "RoutePlanner",
    "TransactionBuilder",
    "PlaceholderQuoteProvider",
    "PlaceholderRoutePlanner",
    "PlaceholderTransactionBuilder",
    "PolymarketQuoteTranslator",
}


def _walk_py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def test_execution_service_imports_no_planning_internals():
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
    violations = imported_names & PLANNING_INTERNALS
    assert not violations, (
        f"ExecutionService imports planning internals directly:\n"
        + "\n".join(f"  {name}" for name in violations)
    )


def test_transaction_plan_contains_no_direct_venue_field():
    from app.domain.planning import TransactionPlan
    field_names = set(TransactionPlan.model_fields.keys())
    assert "venue" not in field_names, (
        f"TransactionPlan must not contain a venue field directly. Found: {field_names}"
    )


def test_planner_imports_no_adapters():
    for filepath in _walk_py_files(PLANNING_SERVICE_DIR):
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "app.exchanges" in alias.name or alias.name.startswith("app.exchanges"):
                        pytest.fail(f"{filepath} imports adapter module: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and ("app.exchanges" in node.module or node.module.startswith("app.exchanges")):
                    pytest.fail(f"{filepath} imports adapter module: {node.module}")


def test_domain_planning_models_have_no_polymarket_fields():
    violations = []
    for filepath in _walk_py_files(PLANNING_DOMAIN_DIR):
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        for token in ("outcome", "condition_id", "clob", "yes_no", "probability"):
            if token in content:
                violations.append((filepath, token))
    assert not violations, (
        "Domain planning models contain Polymarket-specific fields:\n"
        + "\n".join(f"  {path}: {token}" for path, token in violations)
    )


def test_domain_planning_imports_only_pydantic_and_domain():
    stdlib_prefixes = {"decimal", "abc", "datetime", "typing"}
    for filepath in _walk_py_files(PLANNING_DOMAIN_DIR):
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if "pydantic" not in module and "app.domain" not in module and module not in stdlib_prefixes:
                        pytest.fail(f"{filepath} imports non-domain dependency: {module}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and "pydantic" not in node.module and "app.domain" not in node.module and node.module not in stdlib_prefixes:
                    pytest.fail(f"{filepath} imports non-domain dependency: {node.module}")


def test_planning_service_interfaces_import_only_domain():
    interface_files = {"quote_provider.py", "route_planner.py", "transaction_builder.py"}
    allowed_prefixes = {"app.domain", "abc", "decimal"}
    for filepath in _walk_py_files(PLANNING_SERVICE_DIR):
        fname = os.path.basename(filepath)
        if fname not in interface_files:
            continue
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not any(alias.name.startswith(p) for p in allowed_prefixes):
                        pytest.fail(f"{filepath} imports outside domain/abc: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and not any(node.module.startswith(p) for p in allowed_prefixes):
                    pytest.fail(f"{filepath} imports outside domain/abc: {node.module}")


def test_polymarket_translator_only_compatibility_path():
    translator_file = os.path.join(PLANNING_SERVICE_DIR, "translators", "polymarket_quote_translator.py")
    assert os.path.isfile(translator_file), "Polymarket quote translator must exist"
    with open(translator_file, encoding="utf-8") as f:
        content = f.read()
    assert "outcome" in content or "probability" in content, (
        "Polymarket translator must reference legacy Polymarket concepts"
    )
