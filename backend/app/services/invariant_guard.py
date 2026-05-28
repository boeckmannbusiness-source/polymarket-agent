from app.core.logging import logger

VALID_OUTCOMES = {"YES", "NO"}
VALID_SIDES = {"buy", "sell"}


dead_letter_signals: list[dict] = []


def validate_signal_fields(data: dict) -> list[str]:
    errors = []

    signal_id = data.get("signal_id")
    if not signal_id:
        errors.append("signal_id is missing")

    market_id = data.get("market_id") or data.get("market_condition_id")
    if not market_id:
        errors.append("market_id is missing")

    outcome = data.get("outcome")
    if outcome not in VALID_OUTCOMES:
        errors.append(f"outcome must be in {VALID_OUTCOMES}, got {outcome!r}")

    side = data.get("side")
    if side not in VALID_SIDES:
        errors.append(f"side must be in {VALID_SIDES}, got {side!r}")

    size = data.get("size")
    if size is None:
        errors.append("size is missing")
    elif not isinstance(size, (int, float)) or size <= 0:
        errors.append(f"size must be > 0, got {size!r}")

    confidence = data.get("confidence")
    if confidence is not None:
        try:
            cf = float(confidence)
            if cf < 0 or cf > 1:
                errors.append(f"confidence must be in [0, 1], got {cf}")
        except (ValueError, TypeError):
            errors.append(f"confidence is not a valid number: {confidence!r}")

    strategy = data.get("strategy")
    if not strategy:
        errors.append("strategy is missing or empty")

    return errors
