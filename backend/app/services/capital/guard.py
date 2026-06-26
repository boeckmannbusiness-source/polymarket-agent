from app.domain.capital.models import CapitalDecision, RiskReceipt


class CapitalGuard:
    """
    Enforces the global capital_enabled = false rule.
    Even if simulation and admission are approved, capital remains impossible.
    """
    def __init__(self, capital_enabled: bool = False):
        self.capital_enabled = capital_enabled

    def enforce(self, receipt: RiskReceipt) -> RiskReceipt:
        if not self.capital_enabled:
            # Overwrite decision to BLOCK if capital is disabled
            if receipt.capital_decision != CapitalDecision.BLOCK:
                receipt.capital_decision = CapitalDecision.BLOCK
                if "CAPITAL_DISABLED" not in receipt.reason_codes:
                    receipt.reason_codes.append("CAPITAL_DISABLED")
                # Recalculate hash because we modified the decision
                receipt.risk_hash = receipt.calculate_hash()

        return receipt
