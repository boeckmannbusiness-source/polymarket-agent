from decimal import Decimal
from app.domain.capital.models import ExposureReport, ExposureState


class ExposureModel:
    """
    Pure calculation of risk scores and exposure ratios.
    No allocation, no mutation.
    """

    def calculate_exposure(
        self,
        planned_position: Decimal,
        total_capital: Decimal,
        simulated_risk: Decimal,
        asset_class: str = "DEFAULT"
    ) -> ExposureReport:
        if total_capital <= 0:
            return ExposureReport(
                position_ratio=Decimal("1.0"),
                risk_score=Decimal("100.0"),
                exposure_state=ExposureState.REJECT
            )

        position_ratio = (planned_position / total_capital).quantize(Decimal("0.0001"))

        # Risk multiplier based on asset class
        risk_multiplier = Decimal("1.0")
        if asset_class == "MEME":
            risk_multiplier = Decimal("2.0")
        elif asset_class == "MAJOR":
            risk_multiplier = Decimal("0.8")

        # Simple risk score: ratio * simulated_risk factor (0-100) * multiplier
        risk_score = (position_ratio * simulated_risk * risk_multiplier).quantize(Decimal("0.01"))

        # Cap risk score at 100
        if risk_score > Decimal("100.0"):
            risk_score = Decimal("100.0")

        if risk_score > 80 or position_ratio > 0.5:
            state = ExposureState.REJECT
        elif risk_score > 50 or position_ratio > 0.3:
            state = ExposureState.HIGH
        elif risk_score > 20 or position_ratio > 0.1:
            state = ExposureState.MEDIUM
        else:
            state = ExposureState.LOW

        return ExposureReport(
            position_ratio=position_ratio,
            risk_score=risk_score,
            exposure_state=state
        )
