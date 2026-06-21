import ast
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "app")

DOMAIN_DIR = os.path.join(ROOT, "domain", "execution")
EXECUTION_SVC_DIR = os.path.join(ROOT, "services", "execution")
EXECUTION_SERVICE = os.path.join(EXECUTION_SVC_DIR, "execution_service.py")
EXCHANGES_DIR = os.path.join(ROOT, "exchanges")
TRANSLATORS_DIR = os.path.join(EXECUTION_SVC_DIR, "translators")

POLYMARKET_MODULES = {
    "app.exchanges.polymarket_client",
    "app.exchanges.polymarket_live",
}

POLYMARKET_NAMES = {
    "PolymarketClobClient",
    "PolymarketLiveAdapter",
    "polymarket_client",
    "polymarket_live",
}


def _module_path(filepath):
    rel = os.path.relpath(filepath, ROOT)
    return rel.replace(os.sep, ".").replace(".py", "")


def test_domain_models_have_no_polymarket_fields():
    violations = []
    for fname in os.listdir(DOMAIN_DIR):
        if not fname.endswith(".py") or fname == "__init__.py":
            continue
        filepath = os.path.join(DOMAIN_DIR, fname)
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        for token in ("outcome", "condition_id", "clob", "yes_no", "probability"):
            if token in content:
                # Allow compat_ prefix
                if f"compat_{token}" in content:
                    # Simple check: if all occurrences are prefixed with compat_
                    occurrences = content.count(token)
                    compat_occurrences = content.count(f"compat_{token}")
                    if occurrences == compat_occurrences:
                        continue
                violations.append((filepath, token))
    assert not violations, (
        "Domain models contain Polymarket-specific fields:\n" +
        "\n".join(f"  {path}: {token}" for path, token in violations)
    )


def test_execution_service_imports_no_exchange_implementation():
    with open(EXECUTION_SERVICE, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=EXECUTION_SERVICE)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    violations = [
        m for m in imports if m.startswith("app.exchanges.")
        and "ExchangeAdapterRegistry" not in m
        and "BaseExchangeAdapter" not in m
    ]
    assert not violations, (
        f"ExecutionService imports exchange implementations directly:\n" +
        "\n".join(f"  {m}" for m in violations)
    )


def test_translators_are_only_polymarket_bridge():
    for fname in os.listdir(TRANSLATORS_DIR):
        if not fname.endswith(".py") or fname == "__init__.py":
            continue
        filepath = os.path.join(TRANSLATORS_DIR, fname)
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = node.names[0].name if isinstance(node, ast.Import) else node.module
                if module and module.startswith("app.exchanges."):
                    pytest.fail(
                        f"{_module_path(filepath)} imports exchange module '{module}'. "
                        "Translators must not import exchange modules directly."
                    )


def test_execution_service_no_direct_polymarket_reference():
    with open(EXECUTION_SERVICE, encoding="utf-8") as f:
        content = f.read()
    with open(EXECUTION_SERVICE, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=EXECUTION_SERVICE)
    names_in_ast = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names_in_ast.add(node.id)
    for token in ("PolymarketClobClient", "PolymarketLiveAdapter", "polymarket_client", "polymarket_live"):
        if token in names_in_ast or token in content:
            pytest.fail(f"ExecutionService references '{token}' directly. Must use ExchangeAdapterRegistry.")
