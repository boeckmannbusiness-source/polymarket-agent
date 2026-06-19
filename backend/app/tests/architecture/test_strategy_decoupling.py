import ast
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "app")
STRATEGIES_DIR = os.path.join(ROOT, "strategies")
DOMAIN_SIGNALS_DIR = os.path.join(ROOT, "domain", "signals")
EXECUTION_SERVICE_FILE = os.path.join(ROOT, "services", "execution", "execution_service.py")

EXCLUDED_DIRS = {"__pycache__", ".venv", "venv", "env"}


def _walk_py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def test_no_strategy_imports_polymarket_adapters():
    violations = []
    for filepath in _walk_py_files(STRATEGIES_DIR):
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "exchanges" in alias.name or ("polymarket" in alias.name.lower() and "signal" not in alias.name.lower()):
                        violations.append((filepath, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and ("exchanges" in node.module or ("polymarket" in node.module.lower() and "signal" not in node.module.lower())):
                    violations.append((filepath, node.module))
    assert not violations, (
        "Strategies must not import exchange or Polymarket modules:\n" +
        "\n".join(f"  {path}: {mod}" for path, mod in violations)
    )


def test_no_strategy_references_forbidden_domain_fields():
    forbidden = {"condition_id", "clob"}
    violations = []
    for filepath in _walk_py_files(STRATEGIES_DIR):
        if filepath.endswith("signal.py"):
            continue
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                violations.append((filepath, node.id, node.lineno))
    assert not violations, (
        "Strategies must not reference Polymarket-specific fields:\n" +
        "\n".join(f"  {path}:{lineno}: {token}" for path, token, lineno in violations)
    )


def test_domain_signal_imports_no_exchange_code():
    for filepath in _walk_py_files(DOMAIN_SIGNALS_DIR):
        with open(filepath, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=filepath)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "exchange" in alias.name or "polymarket" in alias.name.lower():
                        pytest.fail(f"{filepath} imports exchange code: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and ("exchange" in node.module or "polymarket" in node.module.lower()):
                    pytest.fail(f"{filepath} imports exchange code: {node.module}")


def test_execution_service_accepts_signal():
    with open(EXECUTION_SERVICE_FILE, encoding="utf-8") as f:
        content = f.read()
    assert "from app.domain.signals import Signal" in content or "from app.domain.signals" in content, (
        "ExecutionService must import domain Signal"
    )
    assert "async def execute_signal" in content, (
        "ExecutionService must have execute_signal method"
    )


def test_domain_signal_has_no_polymarket_fields():
    from app.domain.signals import Signal, SignalResult
    forbidden = {"outcome", "probability", "condition_id", "clob_asset_id", "yes_no"}
    for cls in (Signal, SignalResult):
        field_names = set(cls.model_fields.keys())
        assert not (field_names & forbidden), (
            f"{cls.__name__} contains forbidden fields: {field_names & forbidden}"
        )


def test_domain_signal_action_is_enum():
    from app.domain.signals import SignalAction
    assert hasattr(SignalAction, "BUY")
    assert hasattr(SignalAction, "SELL")
    assert hasattr(SignalAction, "HOLD")
    assert "BUY_YES" not in dir(SignalAction)
    assert "BUY_NO" not in dir(SignalAction)


def test_polymarket_translator_legacy_output_contains_no_domain_fields():
    from app.domain.signals import Signal, SignalAction
    from app.domain.execution.instrument import Instrument
    from app.services.signals.translators import PolymarketSignalTranslator

    domain_signal = Signal(
        instrument=Instrument(venue="test", symbol="s", asset_identifier="a", quote_asset="USDC"),
        action=SignalAction.BUY,
        confidence=0.8,
    )
    structured = PolymarketSignalTranslator.to_structured(domain_signal)
    assert structured.signal in ("BUY_YES", "BUY_NO", "NEUTRAL")
    assert structured.confidence == 0.8


def test_polymarket_translator_from_structured():
    from app.domain.signals import SignalAction
    from app.services.signals.translators import PolymarketSignalTranslator
    from app.strategies.signal import StructuredSignal

    structured = StructuredSignal(
        strategy="test",
        signal="BUY_YES",
        confidence=0.75,
        market_id="m1",
        reason="test",
    )
    domain_signal = PolymarketSignalTranslator.from_structured(structured)
    assert domain_signal.action == SignalAction.BUY
    assert domain_signal.confidence == 0.75
